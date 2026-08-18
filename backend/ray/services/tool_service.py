"""Persistence for tool calls and standing permissions (ADR-0014).

The approval gate is a *row*, not a prompt instruction: a side-effecting tool runs
only when a `tool_invocations` row for exactly that payload is in `approved` state.
Keeping that here rather than in the Tool Manager holds the layering rule — only
services touch the database — and means the audit log cannot be bypassed by a caller
that forgets to write it.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.models import ToolInvocation, ToolPermission
from ray.domain.enums import InvocationStatus, PermissionMode
from ray.schemas import ToolInvocationRead, ToolPermissionRead


async def permission_mode(
    session: AsyncSession, user_id: uuid.UUID, tool_name: str
) -> PermissionMode:
    """No row means ``ask``: a tool is never implicitly trusted."""
    stmt = select(ToolPermission.mode).where(
        ToolPermission.user_id == user_id, ToolPermission.tool_name == tool_name
    )
    mode = (await session.execute(stmt)).scalar_one_or_none()
    return mode or PermissionMode.ASK


async def set_permission(
    session: AsyncSession, user_id: uuid.UUID, tool_name: str, mode: PermissionMode
) -> ToolPermissionRead:
    stmt = select(ToolPermission).where(
        ToolPermission.user_id == user_id, ToolPermission.tool_name == tool_name
    )
    permission = (await session.execute(stmt)).scalar_one_or_none()
    if permission is None:
        permission = ToolPermission(user_id=user_id, tool_name=tool_name, mode=mode)
        session.add(permission)
    else:
        permission.mode = mode
    await session.flush()
    return ToolPermissionRead(tool_name=tool_name, mode=mode)


async def list_permissions(session: AsyncSession, user_id: uuid.UUID) -> dict[str, PermissionMode]:
    stmt = select(ToolPermission).where(ToolPermission.user_id == user_id)
    return {p.tool_name: p.mode for p in (await session.execute(stmt)).scalars()}


async def record(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    tool_name: str,
    payload: dict[str, object],
    side_effect: bool,
    status: InvocationStatus,
    conversation_id: uuid.UUID | None = None,
    result: dict[str, object] | None = None,
    error: str | None = None,
) -> ToolInvocation:
    """Log a call. Every invocation lands here, successful or not."""
    invocation = ToolInvocation(
        user_id=user_id,
        conversation_id=conversation_id,
        tool_name=tool_name,
        payload=payload,
        side_effect=side_effect,
        status=status,
        result=result,
        error=error,
        decided_at=None if status is InvocationStatus.PENDING_APPROVAL else datetime.now(UTC),
    )
    session.add(invocation)
    await session.flush()
    return invocation


async def get_pending(
    session: AsyncSession, user_id: uuid.UUID, invocation_id: uuid.UUID
) -> ToolInvocation | None:
    """Only a pending row can be decided.

    Ownership and status are checked in the query rather than after it, so an
    already-executed invocation cannot be replayed by re-posting the approval.
    """
    stmt = select(ToolInvocation).where(
        ToolInvocation.id == invocation_id,
        ToolInvocation.user_id == user_id,
        ToolInvocation.status == InvocationStatus.PENDING_APPROVAL,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_pending(session: AsyncSession, user_id: uuid.UUID) -> list[ToolInvocationRead]:
    stmt = (
        select(ToolInvocation)
        .where(
            ToolInvocation.user_id == user_id,
            ToolInvocation.status == InvocationStatus.PENDING_APPROVAL,
        )
        .order_by(ToolInvocation.created_at.asc())
    )
    return [ToolInvocationRead.model_validate(i) for i in (await session.execute(stmt)).scalars()]


async def list_recent(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int = 20
) -> list[ToolInvocationRead]:
    stmt = (
        select(ToolInvocation)
        .where(ToolInvocation.user_id == user_id)
        .order_by(ToolInvocation.created_at.desc())
        .limit(limit)
    )
    return [ToolInvocationRead.model_validate(i) for i in (await session.execute(stmt)).scalars()]


async def settle(
    invocation: ToolInvocation,
    *,
    status: InvocationStatus,
    result: dict[str, object] | None = None,
    error: str | None = None,
) -> None:
    invocation.status = status
    invocation.result = result
    invocation.error = error
    invocation.decided_at = datetime.now(UTC)
