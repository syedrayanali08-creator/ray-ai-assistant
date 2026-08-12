"""The memory endpoints (docs/05, ADR-0013).

`docs/05` makes user control a principle, not a feature: view, search, edit, delete,
disable categories, and see *why* a memory exists. That is what this router is —
Ray's knowledge is the user's data, and it has to be inspectable and correctable
without a database client.

Note the two searches. ``GET /memory`` filters by substring, because a user hunting
for a memory remembers the words they typed. ``GET /memory/search`` is semantic and
returns the scores, because a user asking "why did Ray say that?" needs to see what
retrieval actually ranked.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.session import get_session
from ray.domain.enums import MemoryCategory, MemorySource
from ray.memory.embeddings import get_embedder
from ray.schemas import (
    MemoryCategorySettings,
    MemoryCreate,
    MemoryRead,
    MemoryScored,
    MemoryStats,
    MemoryUpdate,
)
from ray.security.auth import get_current_user_id
from ray.services import memory_service

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=list[MemoryRead])
async def list_memories(
    category: MemoryCategory | None = None,
    q: str | None = Query(default=None, max_length=300),
    limit: int = Query(default=100, ge=1, le=500),
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[MemoryRead]:
    return await memory_service.list_memories(
        session, user_id, category=category, query=q, limit=limit
    )


@router.get("/search", response_model=list[MemoryScored])
async def search_memories(
    q: str = Query(min_length=1, max_length=1_000),
    limit: int = Query(default=10, ge=1, le=50),
    project_id: uuid.UUID | None = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[MemoryScored]:
    """Semantic search, ranked exactly as retrieval ranks — this is the debugging
    surface for "why does Ray keep bringing that up?"."""
    embedding = (await get_embedder().embed([q]))[0]
    return await memory_service.scored_for_api(
        session, user_id, embedding, limit=limit, project_id=project_id
    )


@router.get("/stats", response_model=MemoryStats)
async def read_stats(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> MemoryStats:
    return await memory_service.stats(session, user_id)


@router.get("/review", response_model=list[MemoryRead])
async def review_queue(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[MemoryRead]:
    """Unimportant, never-retrieved conversation memories. Ray flags; the user
    decides — nothing here is deleted automatically (ADR-0013)."""
    return await memory_service.stale_candidates(session, user_id)


@router.put("/categories", response_model=MemoryCategorySettings)
async def set_categories(
    data: MemoryCategorySettings,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> MemoryCategorySettings:
    """Disabling a category stops both retrieval and future writes in it."""
    disabled = await memory_service.set_disabled_categories(
        session, user_id, data.disabled_categories
    )
    return MemoryCategorySettings(disabled_categories=disabled)


@router.post("", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
async def create_memory(
    data: MemoryCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> MemoryRead:
    """A memory the user wrote themselves, embedded immediately so it is retrievable
    on the very next turn."""
    embedding = (await get_embedder().embed([data.content]))[0]
    memory = await memory_service.create(
        session,
        user_id,
        content=data.content,
        category=data.category,
        importance=data.importance,
        why=data.why or "Added by the user.",
        embedding=embedding,
        source=MemorySource.USER,
        project_id=data.project_id,
    )
    await session.commit()
    return memory


@router.patch("/{memory_id}", response_model=MemoryRead)
async def update_memory(
    memory_id: uuid.UUID,
    data: MemoryUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> MemoryRead:
    # Edited content is re-embedded here rather than in the service, so the service
    # never has to know how vectors are produced.
    embedding = (await get_embedder().embed([data.content]))[0] if data.content else None
    memory = await memory_service.update(
        session,
        user_id,
        memory_id,
        content=data.content,
        category=data.category,
        importance=data.importance,
        why=data.why,
        embedding=embedding,
    )
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return memory


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    if not await memory_service.delete_memory(session, user_id, memory_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
