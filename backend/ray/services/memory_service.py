"""Everything that touches the ``memories`` table (ADR-0013).

Ranking happens *here*, in SQL, rather than in Python: the alternative is loading
every memory into the process to score it, which stops working at the first
interesting corpus size. `ray.memory.scoring` holds the same formula in readable
form, and a test asserts the two agree.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    ColumnElement,
    Float,
    Select,
    case,
    cast,
    func,
    literal,
    or_,
    select,
)
from sqlalchemy import (
    update as sql_update,
)
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.models import Memory, User
from ray.domain.enums import MemoryCategory, MemorySource
from ray.memory.scoring import (
    DEFAULT_WEIGHTS,
    RECENCY_HALF_LIFE_DAYS,
    USAGE_SATURATION,
    MemoryWeights,
)
from ray.schemas import MemoryRead, MemoryScored, MemoryStats

# Every category is on unless the user turns it off (docs/05). Absence of the
# setting means "not configured", not "all disabled".
CATEGORY_SETTINGS_KEY = "disabled_memory_categories"


def _live(user_id: uuid.UUID) -> list[ColumnElement[bool]]:
    """Rows that count as knowledge: this user's, and not superseded by a merge."""
    return [Memory.user_id == user_id, Memory.superseded_by.is_(None)]


async def disabled_categories(session: AsyncSession, user_id: uuid.UUID) -> set[MemoryCategory]:
    user = await session.get(User, user_id)
    if user is None:
        return set()
    raw = user.settings.get(CATEGORY_SETTINGS_KEY, [])
    if not isinstance(raw, list):
        return set()
    return {
        MemoryCategory(value)
        for value in raw
        if isinstance(value, str) and value in set(MemoryCategory)
    }


async def set_disabled_categories(
    session: AsyncSession, user_id: uuid.UUID, categories: list[MemoryCategory]
) -> list[MemoryCategory]:
    """Disabling is a retrieval filter, not a delete: the rows stay, unused."""
    user = await session.get(User, user_id)
    if user is None:
        return []
    # Reassigned rather than mutated: SQLAlchemy does not track in-place JSONB edits.
    user.settings = {**user.settings, CATEGORY_SETTINGS_KEY: sorted({c.value for c in categories})}
    await session.commit()
    return sorted(set(categories), key=lambda c: c.value)


async def list_memories(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    category: MemoryCategory | None = None,
    query: str | None = None,
    limit: int = 100,
) -> list[MemoryRead]:
    """The dashboard listing: newest and most important first.

    ``query`` is a literal substring match, not a semantic one — when the user is
    looking for a memory they half-remember writing, they want the words they typed
    (semantic search is what the *assistant* uses, in ``search``).
    """
    stmt = select(Memory).where(*_live(user_id))
    if category is not None:
        stmt = stmt.where(Memory.category == category)
    if query:
        stmt = stmt.where(Memory.content.ilike(f"%{query}%"))
    stmt = stmt.order_by(Memory.importance.desc(), Memory.updated_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return [MemoryRead.model_validate(m) for m in result.scalars()]


async def stats(session: AsyncSession, user_id: uuid.UUID) -> MemoryStats:
    counts = await session.execute(
        select(Memory.category, func.count()).where(*_live(user_id)).group_by(Memory.category)
    )
    by_category = {category.value: count for category, count in counts.all()}

    superseded = await session.scalar(
        select(func.count())
        .select_from(Memory)
        .where(Memory.user_id == user_id, Memory.superseded_by.is_not(None))
    )
    unembedded = await session.scalar(
        select(func.count()).select_from(Memory).where(*_live(user_id), Memory.embedding.is_(None))
    )
    return MemoryStats(
        total=sum(by_category.values()),
        by_category=by_category,
        superseded=superseded or 0,
        unembedded=unembedded or 0,
        disabled_categories=sorted(await disabled_categories(session, user_id)),
    )


def _score_expression(
    embedding: list[float],
    *,
    project_id: uuid.UUID | None,
    weights: MemoryWeights,
) -> tuple[ColumnElement[float], ColumnElement[float]]:
    """The ADR-0013 hybrid score, as SQL. Returns (similarity, score)."""
    similarity = _similarity(embedding)

    importance = cast(func.least(func.greatest(Memory.importance, 1), 5) - 1, Float) / 4.0
    age_days = func.extract("epoch", func.now() - Memory.updated_at) / 86400.0
    recency = func.power(0.5, age_days / RECENCY_HALF_LIFE_DAYS)
    usage = cast(func.least(Memory.hit_count, USAGE_SATURATION), Float) / float(USAGE_SATURATION)

    score = (
        weights.similarity * similarity
        + weights.importance * importance
        + weights.recency * recency
        + weights.usage * usage
    )
    if project_id is not None:
        score = score + case(
            (Memory.project_id == project_id, literal(weights.project_boost)),
            else_=literal(0.0),
        )
    return similarity, score


def _similarity(embedding: list[float]) -> ColumnElement[float]:
    """pgvector gives cosine *distance*; similarity is its complement."""
    distance: ColumnElement[float] = Memory.embedding.cosine_distance(embedding)
    return literal(1.0) - distance


def _searchable(
    user_id: uuid.UUID,
    stmt: Select[tuple[Memory, float, float]],
    *,
    excluded: set[MemoryCategory],
) -> Select[tuple[Memory, float, float]]:
    stmt = stmt.where(*_live(user_id), Memory.embedding.is_not(None))
    if excluded:
        stmt = stmt.where(Memory.category.not_in(list(excluded)))
    return stmt


async def search(
    session: AsyncSession,
    user_id: uuid.UUID,
    embedding: list[float],
    *,
    limit: int = 5,
    project_id: uuid.UUID | None = None,
    min_score: float = 0.0,
    weights: MemoryWeights = DEFAULT_WEIGHTS,
    categories: set[MemoryCategory] | None = None,
    exclude_categories: set[MemoryCategory] | None = None,
) -> list[tuple[MemoryRead, float, float]]:
    """Hybrid retrieval. Returns (memory, similarity, score), best first."""
    similarity, score = _score_expression(embedding, project_id=project_id, weights=weights)
    stmt = _searchable(
        user_id,
        select(Memory, similarity.label("similarity"), score.label("score")),
        excluded=exclude_categories or set(),
    )
    if categories:
        stmt = stmt.where(Memory.category.in_(list(categories)))
    stmt = stmt.order_by(score.desc()).limit(limit)

    rows = (await session.execute(stmt)).all()
    return [
        (MemoryRead.model_validate(memory), float(row_similarity), float(row_score))
        for memory, row_similarity, row_score in rows
        if float(row_score) >= min_score
    ]


async def nearest_in_category(
    session: AsyncSession,
    user_id: uuid.UUID,
    embedding: list[float],
    category: MemoryCategory,
) -> tuple[Memory, float] | None:
    """The closest live memory in one category, for the dedupe decision.

    Similarity only — a *duplicate* is a duplicate regardless of how important or
    recent the row it duplicates happens to be.
    """
    similarity = _similarity(embedding)
    stmt = (
        select(Memory, similarity.label("similarity"))
        .where(*_live(user_id), Memory.category == category, Memory.embedding.is_not(None))
        .order_by(similarity.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        return None
    memory, value = row
    return memory, float(value)


async def create(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    content: str,
    category: MemoryCategory,
    importance: int,
    why: str = "",
    embedding: list[float] | None = None,
    source: MemorySource = MemorySource.CONVERSATION,
    source_message_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> MemoryRead:
    memory = Memory(
        user_id=user_id,
        content=content,
        category=category,
        importance=max(1, min(5, importance)),
        why=why,
        embedding=embedding,
        source=source,
        source_message_id=source_message_id,
        project_id=project_id,
    )
    session.add(memory)
    await session.flush()
    await session.refresh(memory)
    return MemoryRead.model_validate(memory)


async def update(
    session: AsyncSession,
    user_id: uuid.UUID,
    memory_id: uuid.UUID,
    *,
    content: str | None = None,
    category: MemoryCategory | None = None,
    importance: int | None = None,
    why: str | None = None,
    embedding: list[float] | None = None,
) -> MemoryRead | None:
    memory = await _own(session, user_id, memory_id)
    if memory is None:
        return None
    if content is not None:
        memory.content = content
        # An edited memory whose vector still describes the old text would be
        # retrieved for the wrong questions.
        memory.embedding = embedding
    if category is not None:
        memory.category = category
    if importance is not None:
        memory.importance = max(1, min(5, importance))
    if why is not None:
        memory.why = why
    await session.flush()
    await session.refresh(memory)
    await session.commit()
    return MemoryRead.model_validate(memory)


async def refresh_duplicate(session: AsyncSession, memory_id: uuid.UUID) -> None:
    """A repeated fact is a used fact: bump usage rather than storing it twice."""
    memory = await session.get(Memory, memory_id)
    if memory is None:
        return
    memory.hit_count += 1
    memory.updated_at = datetime.now(UTC)
    await session.flush()


async def supersede(session: AsyncSession, old_id: uuid.UUID, new_id: uuid.UUID) -> None:
    """Point the old row at its replacement instead of deleting it (ADR-0013)."""
    old = await session.get(Memory, old_id)
    if old is not None:
        old.superseded_by = new_id
        await session.flush()


async def record_usage(session: AsyncSession, memory_ids: list[uuid.UUID]) -> None:
    """Retrieval feeds ranking: a memory that keeps being useful outranks one that
    never is. Without this the ``usage`` term of the score is always zero."""
    if not memory_ids:
        return
    now = datetime.now(UTC)
    for memory_id in memory_ids:
        memory = await session.get(Memory, memory_id)
        if memory is not None:
            memory.hit_count += 1
            memory.last_used_at = now
    await session.flush()


async def stale_candidates(
    session: AsyncSession, user_id: uuid.UUID, *, days: int = 90, limit: int = 50
) -> list[MemoryRead]:
    """Low-value conversation memories that have never been used (ADR-0013).

    Flagged for the user to review. Ray does not delete the user's data on its own,
    so this is a query, not a job.
    """
    cutoff = func.now() - func.make_interval(0, 0, 0, days)
    stmt = (
        select(Memory)
        .where(
            *_live(user_id),
            Memory.category == MemoryCategory.CONVERSATION,
            Memory.importance <= 2,
            Memory.hit_count == 0,
            or_(Memory.last_used_at.is_(None), Memory.last_used_at < cutoff),
            Memory.created_at < cutoff,
        )
        .order_by(Memory.created_at)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return [MemoryRead.model_validate(m) for m in result.scalars()]


async def scored_for_api(
    session: AsyncSession,
    user_id: uuid.UUID,
    embedding: list[float],
    *,
    limit: int,
    project_id: uuid.UUID | None,
) -> list[MemoryScored]:
    """Semantic search for the memory view, showing why each result won."""
    found = await search(
        session,
        user_id,
        embedding,
        limit=limit,
        project_id=project_id,
        exclude_categories=await disabled_categories(session, user_id),
    )
    return [
        MemoryScored(memory=memory, similarity=similarity, score=score)
        for memory, similarity, score in found
    ]


async def delete_memory(session: AsyncSession, user_id: uuid.UUID, memory_id: uuid.UUID) -> bool:
    """Hard delete: "delete" must mean deleted (docs/12).

    Rows that were superseded by this one are released rather than cascaded away, so
    deleting a merged memory cannot silently take history with it.
    """
    memory = await _own(session, user_id, memory_id)
    if memory is None:
        return False
    await session.execute(
        sql_update(Memory).where(Memory.superseded_by == memory_id).values(superseded_by=None)
    )
    await session.delete(memory)
    await session.commit()
    return True


async def _own(session: AsyncSession, user_id: uuid.UUID, memory_id: uuid.UUID) -> Memory | None:
    stmt = select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()
