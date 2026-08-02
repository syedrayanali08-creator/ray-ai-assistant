import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ray.db.base import Base, TimestampMixin, uuid_pk
from ray.domain.enums import EventSource


class CalendarEvent(Base, TimestampMixin):
    """A scheduled event.

    ``source`` plus ``external_id`` let the local calendar and a synced external
    calendar coexist without duplicating events (ADR-0010).
    """

    __tablename__ = "calendar_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)

    source: Mapped[EventSource] = mapped_column(default=EventSource.RAY, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Set when the event is a time block for a specific task.
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
