import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.models import CalendarEvent
from ray.domain.enums import EventSource
from ray.schemas import CalendarEventCreate, CalendarEventRead
from ray.services.errors import InvalidEventError


async def list_events(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 100,
) -> list[CalendarEventRead]:
    stmt = select(CalendarEvent).where(CalendarEvent.user_id == user_id)
    # Overlap, not containment: an event that started this morning and runs into
    # this afternoon still belongs in "today".
    if end is not None:
        stmt = stmt.where(CalendarEvent.start_time < end)
    if start is not None:
        stmt = stmt.where(CalendarEvent.end_time > start)
    stmt = stmt.order_by(CalendarEvent.start_time.asc()).limit(limit)
    result = await session.execute(stmt)
    return [CalendarEventRead.model_validate(e) for e in result.scalars()]


async def create_event(
    session: AsyncSession, user_id: uuid.UUID, data: CalendarEventCreate
) -> CalendarEventRead:
    """Create a locally-owned event.

    ``LocalCalendar`` is the default calendar (ADR-0010); a synced Google event is
    never created here, which is why ``source`` is not a parameter.
    """
    if data.end_time <= data.start_time:
        raise InvalidEventError("An event must end after it starts.")
    event = CalendarEvent(user_id=user_id, source=EventSource.RAY, **data.model_dump())
    session.add(event)
    await session.flush()
    return CalendarEventRead.model_validate(event)
