"""Per-topic learning progress (docs/07).

Proficiency is stored rather than inferred per conversation, because the explanation
mode has to be stable: being taught a topic as a beginner today and as an expert
tomorrow is worse than either.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.models import LearningRecord
from ray.domain.enums import Proficiency
from ray.schemas import LearningRecordRead


def _normalise(topic: str) -> str:
    return topic.strip().lower()


async def list_records(session: AsyncSession, user_id: uuid.UUID) -> list[LearningRecordRead]:
    stmt = (
        select(LearningRecord)
        .where(LearningRecord.user_id == user_id)
        .order_by(LearningRecord.updated_at.desc())
    )
    return [LearningRecordRead.model_validate(r) for r in (await session.execute(stmt)).scalars()]


async def get_record(
    session: AsyncSession, user_id: uuid.UUID, topic: str
) -> LearningRecordRead | None:
    record = await _find(session, user_id, topic)
    return None if record is None else LearningRecordRead.model_validate(record)


async def upsert(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    topic: str,
    proficiency: Proficiency | None = None,
    strengths: str | None = None,
    weaknesses: str | None = None,
    notes: str | None = None,
    reviewed: bool = True,
) -> LearningRecordRead:
    """Create or update one topic.

    Upsert rather than create/update: the Learning Agent knows the topic it just
    taught, not whether Ray has seen it before, and making it check first would be a
    round trip that adds nothing.
    """
    record = await _find(session, user_id, topic)
    if record is None:
        record = LearningRecord(user_id=user_id, topic=topic.strip())
        session.add(record)
    if proficiency is not None:
        record.proficiency = proficiency
    if strengths is not None:
        record.strengths = strengths
    if weaknesses is not None:
        record.weaknesses = weaknesses
    if notes is not None:
        record.notes = notes
    if reviewed:
        record.last_reviewed = datetime.now(UTC)
    await session.flush()
    return LearningRecordRead.model_validate(record)


async def _find(session: AsyncSession, user_id: uuid.UUID, topic: str) -> LearningRecord | None:
    # Case-insensitive: "Recursion" and "recursion" are one topic, and the agent
    # capitalises inconsistently.
    stmt = select(LearningRecord).where(
        LearningRecord.user_id == user_id,
        func.lower(LearningRecord.topic) == _normalise(topic),
    )
    return (await session.execute(stmt)).scalars().first()
