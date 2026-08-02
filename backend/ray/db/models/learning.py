import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ray.db.base import Base, TimestampMixin, uuid_pk
from ray.domain.enums import Proficiency


class LearningRecord(Base, TimestampMixin):
    """Per-topic progress.

    ``proficiency`` selects the explanation mode in docs/07 directly, rather than
    the mode being guessed per conversation.
    """

    __tablename__ = "learning_records"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    proficiency: Mapped[Proficiency] = mapped_column(default=Proficiency.NONE, nullable=False)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    weaknesses: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_reviewed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
