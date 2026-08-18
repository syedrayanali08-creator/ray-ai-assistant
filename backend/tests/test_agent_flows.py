"""Specialist agent flows: the agent loop calls tools and emits trace events."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ray.agents.base import AgentContext, AgentFinished, AgentToken
from ray.agents.planning import PlanningAgent
from ray.config import get_settings
from ray.domain.enums import Modality
from ray.llm.registry import ProviderRegistry
from ray.tools.manager import AgentToolbox, ToolContext, get_manager
from tests.fakes import FakeProvider


def _settings():
    # Route to the fake test double, never to a real model.
    return get_settings().model_copy(update={"llm_provider": "mock", "llm_fallback_provider": None})


async def _run_agent(agent, ctx: AgentContext) -> tuple[str, list[str]]:
    text = ""
    tool_names: list[str] = []
    async for event in agent.run(ctx):
        if isinstance(event, AgentToken):
            text += event.text
        elif isinstance(event, AgentFinished):
            text = event.content
    for result in ctx.tools.results:
        tool_names.append(result.tool)
    return text, tool_names


async def test_planning_agent_calls_task_list(session: AsyncSession, user_id: uuid.UUID) -> None:
    """A planning request routes to the Planning Agent and reads the user's tasks."""
    provider = FakeProvider(
        ["Done."],
        tool_routing={"tasks.list": {}},
    )
    registry = ProviderRegistry(_settings())
    registry.register("mock", provider)

    manager = get_manager()
    ctx = AgentContext(
        user_id=user_id,
        user_name="Rayan",
        message="Plan my week",
        history=[],
        tools=AgentToolbox(manager, ToolContext(session=session, user_id=user_id)),
        output_modality=Modality.TEXT,
    )
    agent = PlanningAgent(registry)

    text, tools = await _run_agent(agent, ctx)

    assert "tasks.list" in tools
    assert text
    assert provider.calls
    # The first planning decision offered the tool, the second streamed the answer.
    assert any(c.tools for c in provider.calls)
