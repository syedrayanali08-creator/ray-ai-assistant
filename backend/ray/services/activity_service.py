"""Agent activity log.

Agents are code, but what they did is data (ADR-0005). This is the only writer.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.models import AgentActivity


async def record_activity(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    agent_name: str,
    action: str,
    summary: str,
    duration_ms: int,
    success: bool,
) -> None:
    session.add(
        AgentActivity(
            user_id=user_id,
            conversation_id=conversation_id,
            agent_name=agent_name,
            action=action,
            summary=summary[:200],
            duration_ms=duration_ms,
            success=success,
        )
    )
