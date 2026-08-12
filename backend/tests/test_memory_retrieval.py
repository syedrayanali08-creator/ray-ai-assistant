"""Retrieval behaviour: filters, ranking, ownership, and the deletion guarantee."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from ray.config import get_settings
from ray.db.models import Memory, Project, User
from ray.domain.enums import MemoryCategory
from ray.memory.embeddings import HashingEmbedder
from ray.memory.retrieval import PgVectorRetriever
from ray.services import memory_service

EMBEDDER = HashingEmbedder()

GAME = "The user is building a Processing game called Starfall Sprint"
PIZZA = "The user dislikes pineapple on pizza"


async def _add(
    session: AsyncSession,
    user_id: uuid.UUID,
    content: str,
    *,
    category: MemoryCategory = MemoryCategory.PROJECT,
    importance: int = 3,
    hit_count: int = 0,
    project_id: uuid.UUID | None = None,
    embed: bool = True,
    age_days: float = 0.0,
) -> Memory:
    memory = Memory(
        user_id=user_id,
        category=category,
        content=content,
        importance=importance,
        hit_count=hit_count,
        project_id=project_id,
        embedding=(await EMBEDDER.embed([content]))[0] if embed else None,
    )
    if age_days:
        stale = datetime.now(UTC) - timedelta(days=age_days)
        memory.created_at = stale
        memory.updated_at = stale
    session.add(memory)
    await session.commit()
    return memory


def _retriever() -> PgVectorRetriever:
    return PgVectorRetriever(embedder=EMBEDDER)


async def test_a_relevant_memory_is_retrieved(session: AsyncSession, user_id: uuid.UUID) -> None:
    await _add(session, user_id, GAME)
    found = await _retriever().retrieve(session, user_id, "What Processing game am I building?")
    assert [m.content for m in found] == [GAME]
    assert found[0].similarity > 0.4


async def test_an_irrelevant_memory_is_left_out(session: AsyncSession, user_id: uuid.UUID) -> None:
    """The min-score floor: a weak match spends context and misleads the model."""
    await _add(session, user_id, PIZZA, category=MemoryCategory.USER)
    found = await _retriever().retrieve(session, user_id, "Which Processing game am I building?")
    assert found == []


async def test_another_users_memories_are_invisible(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    other = User(name="Other", email="other@example.com", preferences={}, settings={})
    session.add(other)
    await session.commit()
    await _add(session, other.id, GAME)

    assert await _retriever().retrieve(session, user_id, "Processing game") == []
    assert len(await _retriever().retrieve(session, other.id, "Processing game")) == 1


async def test_a_disabled_category_is_not_retrieved(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _add(session, user_id, GAME)
    assert len(await _retriever().retrieve(session, user_id, "Processing game")) == 1

    await memory_service.set_disabled_categories(session, user_id, [MemoryCategory.PROJECT])
    assert await _retriever().retrieve(session, user_id, "Processing game") == []


async def test_a_superseded_memory_is_not_retrieved(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    old = await _add(session, user_id, GAME)
    new = await _add(session, user_id, f"{GAME} with mouse aiming")
    await memory_service.supersede(session, old.id, new.id)
    await session.commit()

    found = await _retriever().retrieve(session, user_id, "Processing game")
    assert [m.id for m in found] == [new.id]


async def test_deleting_a_memory_stops_ray_using_it_immediately(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    """A Phase 3 completion criterion, and the whole point of user control."""
    memory = await _add(session, user_id, GAME)
    assert len(await _retriever().retrieve(session, user_id, "Processing game")) == 1

    assert await memory_service.delete_memory(session, user_id, memory.id) is True
    assert await _retriever().retrieve(session, user_id, "Processing game") == []


async def test_an_unembedded_memory_cannot_be_retrieved(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    """It is still the user's data and still listed — just not searchable."""
    await _add(session, user_id, GAME, embed=False)
    assert await _retriever().retrieve(session, user_id, "Processing game") == []
    assert len(await memory_service.list_memories(session, user_id)) == 1


async def test_retrieval_records_usage(session: AsyncSession, user_id: uuid.UUID) -> None:
    memory = await _add(session, user_id, GAME)
    await _retriever().retrieve(session, user_id, "Processing game")
    await session.commit()
    await session.refresh(memory)

    assert memory.hit_count == 1
    assert memory.last_used_at is not None


async def test_the_active_project_outranks_an_equally_similar_memory(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    project = Project(user_id=user_id, name="Starfall Sprint", description="", technology_stack=[])
    session.add(project)
    await session.commit()

    await _add(session, user_id, f"{GAME} in the evenings")
    scoped = await _add(session, user_id, f"{GAME} for a class", project_id=project.id)

    found = await _retriever().retrieve(session, user_id, "Processing game", project_id=project.id)
    assert found[0].id == scoped.id


async def test_a_recent_memory_outranks_a_stale_identical_one(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _add(session, user_id, f"{GAME}, updated last year", age_days=365)
    fresh = await _add(session, user_id, f"{GAME}, updated today")

    found = await _retriever().retrieve(session, user_id, "Processing game")
    assert found[0].id == fresh.id


async def test_the_context_budget_caps_what_reaches_the_prompt(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    for index in range(4):
        # Long but genuinely relevant, so the budget is what excludes them.
        await _add(session, user_id, f"{GAME}, note {index}. " * 3)

    settings = get_settings().model_copy(update={"memory_context_chars": 260, "memory_top_k": 4})
    found = await PgVectorRetriever(embedder=EMBEDDER, settings=settings).retrieve(
        session, user_id, "Processing game"
    )
    # Only one of these fits in the budget; the rest are dropped whole.
    assert len(found) == 1


async def test_top_k_bounds_the_result_set(session: AsyncSession, user_id: uuid.UUID) -> None:
    for index in range(8):
        await _add(session, user_id, f"{GAME}, variant {index}")

    settings = get_settings().model_copy(update={"memory_top_k": 3})
    found = await PgVectorRetriever(embedder=EMBEDDER, settings=settings).retrieve(
        session, user_id, "Processing game"
    )
    assert len(found) == 3
    # Best first, so a truncated prompt keeps the most useful memories.
    assert found == sorted(found, key=lambda m: m.score, reverse=True)


async def test_stale_low_value_memories_are_flagged_not_deleted(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    stale = await _add(
        session,
        user_id,
        "The user asked about the weather in Toronto",
        category=MemoryCategory.CONVERSATION,
        importance=1,
        age_days=120,
    )
    await _add(session, user_id, GAME, importance=5)

    flagged = await memory_service.stale_candidates(session, user_id)
    assert [m.id for m in flagged] == [stale.id]
    # Flagging is a query, not a deletion: the row is still there.
    assert len(await memory_service.list_memories(session, user_id)) == 2
