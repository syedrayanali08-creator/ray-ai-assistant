"""The Tool Manager, internal tools, and approval gate (ADR-0010, ADR-0014)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ray.tools.manager import ToolContext, ToolManager


def _manager() -> ToolManager:
    """A fresh manager with the internal tools registered."""
    from ray.tools.internal import INTERNAL_TOOLS

    manager = ToolManager()
    for tool in INTERNAL_TOOLS:
        manager.register(tool)
    return manager


async def test_unknown_tool_is_a_failed_result() -> None:
    manager = _manager()
    ctx = ToolContext(session=None, user_id=uuid.uuid4())  # type: ignore[arg-type]
    result = await manager.invoke(ctx, "not.a.tool", {}, allowed=["tasks.list"])
    assert result.status == "failed"


async def test_tool_not_allowed_for_agent_is_denied(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    manager = _manager()
    ctx = ToolContext(session=session, user_id=user_id)
    result = await manager.invoke(ctx, "tasks.create", {"title": "x"}, allowed=["tasks.list"])
    assert result.status == "denied"


async def test_side_effecting_tool_requires_approval(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    manager = _manager()
    ctx = ToolContext(session=session, user_id=user_id)
    result = await manager.invoke(
        ctx, "tasks.create", {"title": "Review Phase 4"}, allowed=["tasks.create"]
    )
    assert result.status == "pending_approval"
    assert result.invocation_id is not None
    # The payload is stored exactly, so the approval card matches what will run.
    assert result.data["payload"] == {"title": "Review Phase 4"}


async def test_approve_executes_the_stored_payload(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    manager = _manager()
    ctx = ToolContext(session=session, user_id=user_id)
    result = await manager.invoke(
        ctx, "tasks.create", {"title": "Review Phase 4"}, allowed=["tasks.create"]
    )
    assert result.invocation_id is not None

    executed = await manager.execute_approved(session, user_id, result.invocation_id)
    assert executed is not None
    assert executed.status == "executed"
    assert executed.data["task"]["title"] == "Review Phase 4"


async def test_replay_is_blocked_after_execution(session: AsyncSession, user_id: uuid.UUID) -> None:
    manager = _manager()
    ctx = ToolContext(session=session, user_id=user_id)
    result = await manager.invoke(
        ctx, "tasks.create", {"title": "Review Phase 4"}, allowed=["tasks.create"]
    )
    assert result.invocation_id is not None
    await manager.execute_approved(session, user_id, result.invocation_id)
    replay = await manager.execute_approved(session, user_id, result.invocation_id)
    assert replay is None


async def test_reject_prevents_execution(session: AsyncSession, user_id: uuid.UUID) -> None:
    manager = _manager()
    ctx = ToolContext(session=session, user_id=user_id)
    result = await manager.invoke(
        ctx, "tasks.create", {"title": "Review Phase 4"}, allowed=["tasks.create"]
    )
    assert result.invocation_id is not None
    assert await manager.reject(session, user_id, result.invocation_id) is True
    replay = await manager.execute_approved(session, user_id, result.invocation_id)
    assert replay is None
