import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.session import get_session
from ray.schemas import AgentRead
from ray.security.auth import get_current_user_id
from ray.services import agent_service

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentRead])
async def list_agents(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[AgentRead]:
    """List the agents Ray has.

    Agents are defined in code (ADR-0005); this reports the registry plus the
    user's enable/disable state, not database-defined behaviour.
    """
    return await agent_service.list_agents(session, user_id)
