import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ray.db.base import Base, TimestampMixin, uuid_pk


class AgentConfig(Base, TimestampMixin):
    """Runtime state for an agent — not its definition.

    Agents are code (ADR-0005); prompts live in versioned files. This table only
    records what the user has changed at runtime.
    """

    __tablename__ = "agent_configs"
    __table_args__ = (UniqueConstraint("user_id", "agent_name", name="uq_agent_config_user_agent"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Matches a key in the code-side agent registry.
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Provider/model override and any user-appended instructions.
    overrides: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class AgentActivity(Base, TimestampMixin):
    """Audit log of what agents actually did."""

    __tablename__ = "agent_activity"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
