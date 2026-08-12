"""Extraction, dedupe, and merge — the write path from ADR-0013."""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ray.config import get_settings
from ray.db.models import Memory
from ray.domain.enums import MemoryCategory, MemorySource
from ray.llm.registry import ProviderRegistry
from ray.memory.embeddings import HashingEmbedder
from ray.memory.extraction import MemoryExtractor, forced_candidate, parse_candidates
from ray.memory.scoring import DUPLICATE_THRESHOLD, MERGE_THRESHOLD
from ray.memory.writer import MemoryWriter, merge_content
from ray.services import memory_service
from tests.fakes import FakeProvider

PROCESSING_GAME = "The user is building a Processing game called Starfall Sprint."


def _extraction(candidates: list[dict[str, object]]) -> FakeProvider:
    return FakeProvider([json.dumps(candidates)])


def _writer(provider: FakeProvider) -> MemoryWriter:
    registry = ProviderRegistry()
    for name in ("mock", "gemini", "ollama"):
        registry.register(name, provider)  # type: ignore[arg-type]
    # Extraction is off by default in the suite so background learning never fires
    # from unrelated chat tests; these tests are the ones that want it on.
    settings = get_settings().model_copy(update={"memory_extraction_enabled": True})
    return MemoryWriter(MemoryExtractor(registry), embedder=HashingEmbedder(), settings=settings)


async def _live(session: AsyncSession, user_id: uuid.UUID) -> list[Memory]:
    result = await session.execute(
        select(Memory).where(Memory.user_id == user_id, Memory.superseded_by.is_(None))
    )
    return list(result.scalars())


# -- extraction ------------------------------------------------------------


def test_forced_write_is_recognised_without_a_model_call() -> None:
    candidate = forced_candidate("Ray, remember that I prefer Python over Java")
    assert candidate is not None
    assert candidate.content == "I prefer Python over Java"
    # An explicit instruction is attributed to the user, not to Ray's inference.
    assert candidate.source is MemorySource.USER
    assert candidate.importance >= 4


def test_a_normal_question_is_not_a_forced_write() -> None:
    assert forced_candidate("Do you remember what I said about Java?") is None
    assert forced_candidate("What should I work on next?") is None


def test_fenced_json_is_still_parsed() -> None:
    """Models wrap JSON in fences unprompted; rejecting that loses real memories."""
    text = '```json\n[{"category": "goal", "content": "Waterloo CS", "importance": 5}]\n```'
    candidates = parse_candidates(text)
    assert [c.content for c in candidates] == ["Waterloo CS"]
    assert candidates[0].category is MemoryCategory.GOAL


def test_unparseable_output_yields_nothing_rather_than_raising() -> None:
    assert parse_candidates("I could not find any memories, sorry!") == []
    assert parse_candidates('[{"category": "nonsense", "content": "x"}]') == []
    assert parse_candidates("") == []


async def test_weak_candidates_are_dropped_before_they_reach_the_store() -> None:
    provider = _extraction(
        [
            {"category": "user", "content": "Asked about the weather once", "importance": 1},
            {"category": "user", "content": "The user prefers concise answers", "importance": 4},
        ]
    )
    registry = ProviderRegistry()
    for name in ("mock", "gemini", "ollama"):
        registry.register(name, provider)  # type: ignore[arg-type]

    candidates = await MemoryExtractor(registry).extract(
        user_message="hi", assistant_message="hello"
    )
    assert [c.content for c in candidates] == ["The user prefers concise answers"]


# -- dedupe and merge ------------------------------------------------------


async def test_a_new_fact_is_inserted(session: AsyncSession, user_id: uuid.UUID) -> None:
    writer = _writer(
        _extraction(
            [
                {
                    "category": "project",
                    "content": PROCESSING_GAME,
                    "importance": 4,
                    "why": "Stated directly.",
                }
            ]
        )
    )
    result = await writer.write_exchange(
        session, user_id, user_message="I'm building a game", assistant_message="Nice."
    )
    assert (result.inserted, result.merged, result.duplicates) == (1, 0, 0)

    stored = await _live(session, user_id)
    assert stored[0].why == "Stated directly."
    # Retrievable immediately: an unembedded memory is invisible to search.
    assert stored[0].embedding is not None


async def test_the_same_fact_twice_does_not_become_two_rows(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    writer = _writer(
        _extraction([{"category": "project", "content": PROCESSING_GAME, "importance": 4}])
    )
    await writer.write_exchange(session, user_id, user_message="a", assistant_message="b")
    second = await writer.write_exchange(session, user_id, user_message="a", assistant_message="b")

    assert second.duplicates == 1
    stored = await _live(session, user_id)
    assert len(stored) == 1
    # The repeat counts as usage, which is what promotes it in ranking.
    assert stored[0].hit_count == 1


async def test_a_near_duplicate_merges_and_supersedes(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _writer(
        _extraction([{"category": "project", "content": PROCESSING_GAME, "importance": 3}])
    ).write_exchange(session, user_id, user_message="a", assistant_message="b")

    updated = "The user is building a Processing game called Starfall Sprint with mouse aiming."
    result = await _writer(
        _extraction([{"category": "project", "content": updated, "importance": 5}])
    ).write_exchange(session, user_id, user_message="a", assistant_message="b")

    assert (result.inserted, result.merged) == (0, 1)
    live = await _live(session, user_id)
    assert len(live) == 1
    assert "mouse aiming" in live[0].content
    # The merged row inherits the higher importance of the two.
    assert live[0].importance == 5

    # The predecessor is kept, pointed at its replacement, so history is auditable.
    all_rows = (
        (await session.execute(select(Memory).where(Memory.user_id == user_id))).scalars().all()
    )
    superseded = [row for row in all_rows if row.superseded_by is not None]
    assert len(superseded) == 1
    assert superseded[0].superseded_by == live[0].id


async def test_an_unrelated_fact_is_not_merged_into_a_neighbour(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _writer(
        _extraction([{"category": "project", "content": PROCESSING_GAME, "importance": 3}])
    ).write_exchange(session, user_id, user_message="a", assistant_message="b")
    await _writer(
        _extraction(
            [
                {
                    "category": "project",
                    "content": "The user is deploying a Rust web server on Fly.io.",
                    "importance": 3,
                }
            ]
        )
    ).write_exchange(session, user_id, user_message="a", assistant_message="b")

    assert len(await _live(session, user_id)) == 2


async def test_thresholds_are_ordered_as_the_adr_states() -> None:
    assert MERGE_THRESHOLD < DUPLICATE_THRESHOLD < 1.0


def test_merging_leads_with_the_newer_statement() -> None:
    merged = merge_content("Player movement is complete", "Mouse aiming is complete")
    assert merged.startswith("Mouse aiming is complete")
    assert "Player movement" in merged
    # A restatement that already contains the old text does not repeat it.
    assert (
        merge_content("uses Processing", "The user uses Processing") == "The user uses Processing"
    )


async def test_a_disabled_category_is_never_written(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    """Disabling has to stop the write, not just hide the row (docs/12)."""
    await memory_service.set_disabled_categories(session, user_id, [MemoryCategory.PROJECT])
    result = await _writer(
        _extraction([{"category": "project", "content": PROCESSING_GAME, "importance": 5}])
    ).write_exchange(session, user_id, user_message="a", assistant_message="b")

    assert result.written == 0
    assert await _live(session, user_id) == []


async def test_a_forced_write_bypasses_extraction_entirely(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    provider = _extraction([{"category": "user", "content": "something inferred", "importance": 5}])
    writer = _writer(provider)
    await writer.write_exchange(
        session,
        user_id,
        user_message="Ray, remember that I use Waterloo's calendar for deadlines",
        assistant_message="Noted.",
    )

    stored = await _live(session, user_id)
    assert [m.content for m in stored] == ["I use Waterloo's calendar for deadlines"]
    # No extraction call was made: the user was explicit.
    assert provider.calls == []


async def test_a_provider_failure_does_not_break_the_turn(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    """Learning is best-effort; the exchange it came from is already finished."""
    from ray.llm.base import ProviderUnavailableError

    provider = FakeProvider(fail_with=ProviderUnavailableError("down", provider="fake"))
    result = await _writer(provider).write_exchange(
        session, user_id, user_message="a", assistant_message="b"
    )
    assert result.written == 0
