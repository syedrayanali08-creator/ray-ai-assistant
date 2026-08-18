import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ray.agents.registry import AGENTS
from ray.db.models import AgentConfig
from ray.schemas import AgentRead


async def _configs(session: AsyncSession, user_id: uuid.UUID) -> dict[str, bool]:
    """Enabled state by agent name. Meant for callers inside the service layer."""
    stmt = select(AgentConfig.agent_name, AgentConfig.enabled).where(AgentConfig.user_id == user_id)
    rows = (await session.execute(stmt)).all()
    return {row[0]: row[1] for row in rows}


async def list_agents(session: AsyncSession, user_id: uuid.UUID) -> list[AgentRead]:
    """Merge the code-side registry with the user's runtime overrides.

    The registry is authoritative about which agents exist; the database only
    answers whether one is switched off (ADR-0005).
    """
    configs = await _configs(session, user_id)

    return [
        AgentRead(
            name=spec.name,
            display_name=spec.display_name,
            description=spec.description,
            enabled=configs.get(spec.name, True),
            tools=list(spec.tools),
        )
        for spec in AGENTS.values()
    ]
