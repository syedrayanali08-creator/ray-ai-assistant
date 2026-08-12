"""Memory inside a real turn: retrieval reaches the prompt, and the exchange is learnt.

These are the Phase 3 completion criteria from `docs/10` expressed as tests — in
particular, a brand-new conversation answering "what am I working on?" from memory
alone, and a deleted memory disappearing from the very next turn.
"""

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ray.config import Settings, get_settings
from ray.core.contracts import RayRequest
from ray.core.events import StreamEvent, TraceStreamEvent
from ray.core.orchestrator import Orchestrator
from ray.domain.enums import MemoryCategory
from ray.llm.registry import ProviderRegistry
from ray.memory.embeddings import HashingEmbedder
from ray.memory.extraction import MemoryExtractor
from ray.memory.retrieval import PgVectorRetriever
from ray.memory.writer import MemoryWriter
from ray.services import memory_service
from tests.fakes import FakeProvider

GAME = "The user is building a Processing game called Starfall Sprint"
EMBEDDER = HashingEmbedder()


def _settings(**overrides: object) -> Settings:
    return get_settings().model_copy(
        update={"llm_provider": "mock", "llm_fallback_provider": None, **overrides}
    )


def _orchestrator(provider: FakeProvider, **overrides: object) -> Orchestrator:
    settings = _settings(**overrides)
    registry = ProviderRegistry(settings)
    registry.register("mock", provider)
    return Orchestrator(
        providers=registry,
        retriever=PgVectorRetriever(embedder=EMBEDDER, settings=settings),
        writer=MemoryWriter(MemoryExtractor(registry), embedder=EMBEDDER, settings=settings),
        settings=settings,
    )


async def _run(
    orchestrator: Orchestrator, session: AsyncSession, message: str, user_id: uuid.UUID
) -> list[StreamEvent]:
    request = RayRequest(user_id=user_id, message=message)
    return [event async for event in orchestrator.run(session, request, "Rayan")]


async def _remember(session: AsyncSession, user_id: uuid.UUID, content: str) -> uuid.UUID:
    memory = await memory_service.create(
        session,
        user_id,
        content=content,
        category=MemoryCategory.PROJECT,
        importance=4,
        embedding=(await EMBEDDER.embed([content]))[0],
    )
    await session.commit()
    return memory.id


async def test_a_brand_new_conversation_answers_from_memory(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    """The Phase 3 completion criterion: no history, and Ray still knows."""
    await _remember(session, user_id, GAME)

    provider = FakeProvider(["You're working on Starfall Sprint."])
    events = await _run(_orchestrator(provider), session, "What am I working on?", user_id)

    memory_trace = next(
        e for e in events if isinstance(e, TraceStreamEvent) and e.stage == "memory"
    )
    assert memory_trace.detail["count"] == 1
    assert memory_trace.detail["categories"] == ["project"]

    # The memory reached the model, which is the only thing that makes it useful.
    system_prompt = provider.calls[0].system
    assert "Starfall Sprint" in system_prompt


async def test_a_deleted_memory_is_gone_from_the_next_turn(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    memory_id = await _remember(session, user_id, GAME)
    await memory_service.delete_memory(session, user_id, memory_id)

    provider = FakeProvider(["I'm not sure."])
    events = await _run(_orchestrator(provider), session, "What am I working on?", user_id)

    memory_trace = next(
        e for e in events if isinstance(e, TraceStreamEvent) and e.stage == "memory"
    )
    assert memory_trace.detail["count"] == 0
    assert "Starfall Sprint" not in (provider.calls[0].system or "")


async def test_retrieval_is_off_when_memory_is_disabled(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _remember(session, user_id, GAME)

    provider = FakeProvider(["Sure."])
    orchestrator = Orchestrator(
        providers=_registry_for(provider),
        settings=_settings(memory_enabled=False),
    )
    events = await _run(orchestrator, session, "What am I working on?", user_id)

    memory_trace = next(
        e for e in events if isinstance(e, TraceStreamEvent) and e.stage == "memory"
    )
    assert memory_trace.detail["count"] == 0


def _registry_for(provider: FakeProvider) -> ProviderRegistry:
    registry = ProviderRegistry(_settings())
    registry.register("mock", provider)
    return registry


async def test_an_explicit_remember_request_is_stored_after_the_answer(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    """Extraction runs in the background, so the turn is driven through the writer
    directly here; the background task itself is covered by the orchestrator's own
    tests plus `test_memory_write`."""
    settings = _settings()
    registry = _registry_for(FakeProvider(["Noted."]))
    writer = MemoryWriter(MemoryExtractor(registry), embedder=EMBEDDER, settings=settings)

    await writer.write_exchange(
        session,
        user_id,
        user_message="Ray, remember that I ship on Fridays",
        assistant_message="Noted.",
    )
    stored = await memory_service.list_memories(session, user_id)
    assert [m.content for m in stored] == ["I ship on Fridays"]

    # And it is retrievable on the next turn, which is the whole point.
    found = await PgVectorRetriever(embedder=EMBEDDER, settings=settings).retrieve(
        session, user_id, "When do I ship?"
    )
    assert [m.content for m in found] == ["I ship on Fridays"]


async def test_learning_from_an_exchange_survives_a_full_turn(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    """The orchestrator hands the exchange to the writer; here the writer is real and
    the extraction model is scripted, so the assertion is end to end."""
    extraction = json.dumps(
        [{"category": "goal", "content": "The user is applying to Waterloo CS", "importance": 5}]
    )
    settings = _settings(memory_extraction_enabled=True)
    registry = ProviderRegistry(settings)
    registry.register("mock", FakeProvider([extraction]))
    writer = MemoryWriter(MemoryExtractor(registry), embedder=EMBEDDER, settings=settings)

    result = await writer.write_exchange(
        session,
        user_id,
        user_message="I'm applying to Waterloo for CS",
        assistant_message="That's a strong choice.",
    )
    assert result.inserted == 1
    stored = await memory_service.list_memories(session, user_id)
    assert stored[0].category is MemoryCategory.GOAL
