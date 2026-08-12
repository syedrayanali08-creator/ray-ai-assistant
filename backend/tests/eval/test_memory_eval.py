"""Runs the memory evaluation set through the real pipeline (`docs/15`).

This is not a unit test of the retriever: each case goes through the orchestrator, so
a regression anywhere between the request and the prompt — scoring, filtering,
budgeting, or the agent forgetting to include memories at all — fails here.

The model is scripted. What is being evaluated is which memories Ray *used*, which is
observable and deterministic; answer quality is judged separately and advisorily.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ray.config import Settings, get_settings
from ray.core.contracts import RayRequest
from ray.core.events import TraceStreamEvent
from ray.core.orchestrator import Orchestrator
from ray.db.models import Memory
from ray.llm.registry import ProviderRegistry
from ray.memory.embeddings import HashingEmbedder
from ray.memory.retrieval import PgVectorRetriever
from ray.services import memory_service
from tests.eval.cases import CASES, MemoryCase
from tests.fakes import FakeProvider

EMBEDDER = HashingEmbedder()


def _settings() -> Settings:
    return get_settings().model_copy(update={"llm_provider": "mock", "llm_fallback_provider": None})


async def _seed(session: AsyncSession, user_id: uuid.UUID, case: MemoryCase) -> dict[str, str]:
    """Insert the case's world and return key → memory id."""
    keys: dict[str, str] = {}
    for seed in case.seed:
        memory = Memory(
            user_id=user_id,
            category=seed.category,
            content=seed.content,
            importance=seed.importance,
            embedding=(await EMBEDDER.embed([seed.content]))[0],
        )
        if seed.days_old:
            stale = datetime.now(UTC) - timedelta(days=seed.days_old)
            memory.created_at = stale
            memory.updated_at = stale
        session.add(memory)
        await session.flush()
        keys[seed.key] = str(memory.id)
    await session.commit()

    if case.disabled_categories:
        await memory_service.set_disabled_categories(
            session, user_id, list(case.disabled_categories)
        )
    for key in case.delete_keys:
        await memory_service.delete_memory(session, user_id, uuid.UUID(keys[key]))
    return keys


@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
async def test_memory_case(case: MemoryCase, session: AsyncSession, user_id: uuid.UUID) -> None:
    keys = await _seed(session, user_id, case)
    settings = _settings()
    provider = FakeProvider(["Understood."])
    registry = ProviderRegistry(settings)
    registry.register("mock", provider)
    orchestrator = Orchestrator(
        providers=registry,
        retriever=PgVectorRetriever(embedder=EMBEDDER, settings=settings),
        settings=settings,
    )

    events = [
        event
        async for event in orchestrator.run(
            session, RayRequest(user_id=user_id, message=case.query), "Rayan"
        )
    ]
    trace = next(e for e in events if isinstance(e, TraceStreamEvent) and e.stage == "memory")
    system_prompt = provider.calls[0].system or ""

    contents = {seed.key: seed.content for seed in case.seed}
    for key in case.expect_keys:
        assert contents[key] in system_prompt, f"{case.id}: expected {key} to be used"
    for key in case.reject_keys:
        assert contents[key] not in system_prompt, f"{case.id}: {key} must not be used"

    if case.expect_top is not None:
        ranked = [
            content
            for content in sorted(contents.items(), key=lambda item: system_prompt.find(item[1]))
            if content[1] in system_prompt
        ]
        assert ranked, f"{case.id}: nothing was retrieved"
        assert ranked[0][0] == case.expect_top

    if case.expect_keys or case.expect_top:
        assert trace.detail["count"] != 0
    if not case.expect_keys and not case.expect_top:
        # A case that only rejects must reject everything it seeded.
        assert all(contents[key] not in system_prompt for key in case.reject_keys)

    # Unused: asserted here so an unseeded key in a case fails loudly rather than
    # silently passing as "not retrieved".
    assert set(case.expect_keys) | set(case.reject_keys) <= set(keys)
