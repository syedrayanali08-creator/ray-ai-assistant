import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ray.db.base import Base, TimestampMixin, uuid_pk
from ray.domain.enums import TaskPriority, TaskStatus

if TYPE_CHECKING:
    from ray.db.models.project import Project


class Task(Base, TimestampMixin):
    """One task model for both life tasks and project tasks (ADR-0004).

    ``project_id`` is nullable: set means the task belongs to a project. Deleting a
    project nulls the reference rather than deleting the task — losing tasks
    silently would be a data-loss bug.
    """

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[TaskStatus] = mapped_column(default=TaskStatus.TODO, nullable=False)
    priority: Mapped[TaskPriority] = mapped_column(default=TaskPriority.MEDIUM, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project | None"] = relationship(back_populates="tasks")
