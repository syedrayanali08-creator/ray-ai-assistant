import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ARRAY, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ray.db.base import Base, TimestampMixin, uuid_pk
from ray.domain.enums import ProjectStatus

if TYPE_CHECKING:
    from ray.db.models.task import Task


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(default=ProjectStatus.ACTIVE, nullable=False)
    technology_stack: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, nullable=False
    )
    goals: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    progress: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # Links a project to a repository so the Coding Agent can read it (Phase 5).
    repo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    tasks: Mapped[list["Task"]] = relationship(back_populates="project", passive_deletes=True)
