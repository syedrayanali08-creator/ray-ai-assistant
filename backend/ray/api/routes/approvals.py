"""Approval gate UI endpoints (ADR-0014).

A side-effecting tool cannot run until the user approves the exact payload stored in
``tool_invocations``. Approving executes the stored payload; rejecting leaves it as
rejected. Re-approving an already-decided row is a 404, which makes replay impossible.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.session import get_session
from ray.domain.enums import PermissionMode
from ray.schemas import ApprovalDecision, ApprovalOutcome, ToolInvocationRead
from ray.security.auth import get_current_user_id
from ray.services import tool_service
from ray.tools.manager import get_manager

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=list[ToolInvocationRead])
async def list_approvals(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[ToolInvocationRead]:
    """All pending approvals for the user."""
    return await tool_service.list_pending(session, user_id)


@router.post("/{invocation_id}/approve", response_model=ApprovalOutcome)
async def approve_invocation(
    invocation_id: uuid.UUID,
    decision: ApprovalDecision,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ApprovalOutcome:
    """Execute the stored payload and, if requested, remember the decision."""
    manager = get_manager()
    invocation = await tool_service.get_pending(session, user_id, invocation_id)
    if invocation is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Approval not found, already decided, or not owned by you.",
        )

    tool = manager.get(invocation.tool_name)
    if tool is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tool no longer registered.")

    result = await manager.execute_approved(session, user_id, invocation_id)
    if result is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Approval not found, already decided, or not owned by you.",
        )

    if result.status != "executed":
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error or "Tool failed to run.",
        )

    if decision.always_allow:
        if not tool.standing_allow_eligible:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"{tool.name!r} writes outside Ray and cannot be auto-approved.",
            )
        await tool_service.set_permission(session, user_id, tool.name, PermissionMode.ALWAYS_ALLOW)
        await session.commit()

    return ApprovalOutcome(
        invocation=ToolInvocationRead.model_validate(invocation),
        message=f"{tool.summary(invocation.payload)} ran successfully.",
    )


@router.post("/{invocation_id}/reject", response_model=ApprovalOutcome)
async def reject_invocation(
    invocation_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ApprovalOutcome:
    """Reject the approval request without executing the payload."""
    manager = get_manager()
    invocation = await tool_service.get_pending(session, user_id, invocation_id)
    if invocation is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Approval not found, already decided, or not owned by you.",
        )

    if not await manager.reject(session, user_id, invocation_id):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Approval not found, already decided, or not owned by you.",
        )

    return ApprovalOutcome(
        invocation=ToolInvocationRead.model_validate(invocation),
        message=f"{invocation.tool_name} was rejected and did not run.",
    )
