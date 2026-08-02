import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ray.db.base import Base, TimestampMixin, uuid_pk
from ray.domain.enums import InvocationStatus, PermissionMode


class ToolInvocation(Base, TimestampMixin):
    """Every tool call, and the approval gate for the ones that change state.

    A side-effecting tool cannot execute without a row here in ``approved`` state
    (ADR-0014). Enforcement lives in the Tool Manager, not in a prompt.
    """

    __tablename__ = "tool_invocations"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Shown verbatim in the approval card, so the user approves the real action.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    side_effect: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[InvocationStatus] = mapped_column(
        default=InvocationStatus.EXECUTED, nullable=False, index=True
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ToolPermission(Base, TimestampMixin):
    """Standing decisions, so Ray stops asking about trusted low-risk tools."""

    __tablename__ = "tool_permissions"
    __table_args__ = (UniqueConstraint("user_id", "tool_name", name="uq_tool_permission"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    mode: Mapped[PermissionMode] = mapped_column(default=PermissionMode.ASK, nullable=False)
