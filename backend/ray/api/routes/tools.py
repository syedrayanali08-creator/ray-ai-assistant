"""Tool and permission management (ADR-0010, ADR-0014).

Agents do not talk to the user directly about permissions. These endpoints let the HUD
render a tool list, a standing-permission switch, and the approval cards for pending
tool calls.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.session import get_session
from ray.schemas import ToolInvocationRead, ToolPermissionUpdate
from ray.security.auth import get_current_user_id
from ray.services import tool_service
from ray.tools.manager import ToolManager, get_manager

router = APIRouter(prefix="/tools", tags=["tools"])


def get_tool_manager() -> ToolManager:
    return get_manager()


@router.get("", response_model=list[dict[str, object]])
async def list_tools() -> list[dict[str, object]]:
    """All registered tools, with descriptions from the code-side registry."""
    manager = get_tool_manager()
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "side_effect": tool.side_effect,
            "standing_allow_eligible": tool.standing_allow_eligible,
        }
        for tool in manager.tools.values()
    ]


@router.get("/permissions", response_model=list[dict[str, object]])
async def list_permissions(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    """The user's current permission mode for each tool."""
    return [
        {"tool_name": name, "mode": mode.value}
        for name, mode in (await tool_service.list_permissions(session, user_id)).items()
    ]


@router.put("/permissions/{tool_name}", status_code=status.HTTP_200_OK)
async def update_permission(
    tool_name: str,
    update: ToolPermissionUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Set a standing permission for a tool. External writes cannot be "always allow"."""
    from ray.domain.enums import PermissionMode

    manager = get_tool_manager()
    tool = manager.get(tool_name)
    if tool is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown tool {tool_name!r}.")

    mode = PermissionMode(update.mode)
    if mode is PermissionMode.ALWAYS_ALLOW and not tool.standing_allow_eligible:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{tool_name!r} writes outside Ray and cannot be auto-approved.",
        )

    await tool_service.set_permission(session, user_id, tool_name, mode)
    return {"tool_name": tool_name, "mode": mode.value}


@router.get("/pending", response_model=list[ToolInvocationRead])
async def list_pending(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[ToolInvocationRead]:
    """Approval cards waiting for the user."""
    return await tool_service.list_pending(session, user_id)
