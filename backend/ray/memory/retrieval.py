"""The retrieval seam (ADR-0013).

Phase 2 ships ``NullRetriever``: the orchestrator already asks for memories, already
emits a ``memory`` trace event, and already threads ``memories_used`` through to the
response — with zero results. Phase 3 replaces the implementation and changes
nothing else.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedMemory:
    id: uuid.UUID
    content: str
    category: str
    # Hybrid score from ADR-0013, surfaced so the HUD can show why a memory won.
    score: float


class Retriever(ABC):
    @abstractmethod
    async def retrieve(
        self,
        user_id: uuid.UUID,
        query: str,
        *,
        limit: int = 5,
        project_id: uuid.UUID | None = None,
    ) -> list[RetrievedMemory]: ...


class NullRetriever(Retriever):
    """Retrieves nothing, honestly. Phase 3 supersedes it."""

    async def retrieve(
        self,
        user_id: uuid.UUID,
        query: str,
        *,
        limit: int = 5,
        project_id: uuid.UUID | None = None,
    ) -> list[RetrievedMemory]:
        return []
