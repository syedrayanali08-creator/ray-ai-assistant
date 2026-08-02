import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.models import Memory
from ray.domain.enums import MemoryCategory
from ray.schemas import MemoryRead

# Phase 1 exposes memories for the dashboard only. Embedding, retrieval scoring,
# and extraction arrive in Phase 3 (ADR-0013).


async def list_memories(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    category: MemoryCategory | None = None,
    limit: int = 100,
) -> list[MemoryRead]:
    stmt = select(Memory).where(
        Memory.user_id == user_id,
        # Superseded rows are history, not knowledge.
        Memory.superseded_by.is_(None),
    )
    if category is not None:
        stmt = stmt.where(Memory.category == category)
    stmt = stmt.order_by(Memory.importance.desc(), Memory.updated_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return [MemoryRead.model_validate(m) for m in result.scalars()]


async def delete_memory(session: AsyncSession, user_id: uuid.UUID, memory_id: uuid.UUID) -> bool:
    """Hard delete: "delete" must mean deleted (docs/12)."""
    stmt = select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
    memory = (await session.execute(stmt)).scalar_one_or_none()
    if memory is None:
        return False
    await session.delete(memory)
    return True
