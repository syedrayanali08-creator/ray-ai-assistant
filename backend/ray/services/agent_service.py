import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ray.agents.registry import AGENTS
from ray.db.models import AgentConfig
from ray.schemas import AgentRead


async def list_agents(session: AsyncSession, user_id: uuid.UUID) -> list[AgentRead]:
    """Merge the code-side registry with the user's runtime overrides.

    The registry is authoritative about which agents exist; the database only
    answers whether one is switched off (ADR-0005).
    """
    stmt = select(AgentConfig).where(AgentConfig.user_id == user_id)
    configs = {c.agent_name: c for c in (await session.execute(stmt)).scalars()}

    return [
        AgentRead(
            name=spec.name,
            display_name=spec.display_name,
            description=spec.description,
            enabled=configs[spec.name].enabled if spec.name in configs else True,
            tools=list(spec.tools),
        )
        for spec in AGENTS.values()
    ]
