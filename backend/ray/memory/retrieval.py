"""Retrieval (ADR-0013).

The seam Phase 2 left: the orchestrator already asked for memories, already emitted
a ``memory`` trace event, and already threaded the results into the prompt — with
nothing to return. This is the implementation, and the pipeline did not change.

``retrieve`` takes the session rather than owning one. Retrieval is part of a turn,
inside that turn's transaction: a retriever that opened its own connection could
read a state the turn has not committed and would double the connection count for
no benefit.
"""

import uuid
from abc import ABC, abstractmethod

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from ray.config import Settings, get_settings
from ray.memory.embeddings import TextEmbedder, get_embedder
from ray.memory.scoring import DEFAULT_WEIGHTS, MemoryWeights, within_budget
from ray.memory.types import RetrievedMemory
from ray.services import memory_service

log = structlog.get_logger()


__all__ = ["NullRetriever", "PgVectorRetriever", "RetrievedMemory", "Retriever", "get_retriever"]


class Retriever(ABC):
    @abstractmethod
    async def retrieve(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        query: str,
        *,
        limit: int | None = None,
        project_id: uuid.UUID | None = None,
    ) -> list[RetrievedMemory]: ...


class NullRetriever(Retriever):
    """Retrieves nothing, honestly.

    Kept as the explicit way to run Ray with memory off — the pipeline behaves as it
    did in Phase 2 rather than needing a flag threaded through it.
    """

    async def retrieve(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        query: str,
        *,
        limit: int | None = None,
        project_id: uuid.UUID | None = None,
    ) -> list[RetrievedMemory]:
        return []


class PgVectorRetriever(Retriever):
    """Hybrid retrieval in one statement: filter, rank, and limit in the database.

    Retrieval also *writes* — a returned memory has its usage recorded, which is the
    ``usage`` term of the score. Without it, "Ray keeps finding this useful" would
    never influence ranking.
    """

    def __init__(
        self,
        *,
        embedder: TextEmbedder | None = None,
        weights: MemoryWeights = DEFAULT_WEIGHTS,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._embedder = embedder or get_embedder()
        self._weights = weights

    async def retrieve(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        query: str,
        *,
        limit: int | None = None,
        project_id: uuid.UUID | None = None,
    ) -> list[RetrievedMemory]:
        settings = self._settings
        vectors = await self._embedder.embed([query])
        if not vectors:
            return []

        found = await memory_service.search(
            session,
            user_id,
            vectors[0],
            limit=limit or settings.memory_top_k,
            project_id=project_id,
            min_score=settings.memory_min_score,
            weights=self._weights,
            exclude_categories=await memory_service.disabled_categories(session, user_id),
        )

        # The prompt has a budget; the search does not know about it. Dropping the
        # tail here rather than lowering the limit keeps ranking and budgeting
        # separate concerns.
        keep = set(
            within_budget(
                [memory.content for memory, _, _ in found],
                char_budget=settings.memory_context_chars,
            )
        )
        selected = [item for item in found if item[0].content in keep]

        await memory_service.record_usage(session, [memory.id for memory, _, _ in selected])
        log.debug(
            "memory.retrieved",
            found=len(found),
            used=len(selected),
            project_scoped=project_id is not None,
        )
        return [
            RetrievedMemory(
                id=memory.id,
                content=memory.content,
                category=memory.category.value,
                score=score,
                similarity=similarity,
                importance=memory.importance,
            )
            for memory, similarity, score in selected
        ]


def get_retriever(settings: Settings | None = None) -> Retriever:
    settings = settings or get_settings()
    return PgVectorRetriever(settings=settings) if settings.memory_enabled else NullRetriever()
