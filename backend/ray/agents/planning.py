"""Planning Agent — tasks, deadlines, priorities, scheduling, time blocking."""

from ray.agents.registry import get_agent_spec
from ray.agents.tool_agent import ToolUsingAgent
from ray.tools.types import ToolResult


class PlanningAgent(ToolUsingAgent):
    spec = get_agent_spec("planning")
    prompt_name = "planning"

    def _render_tool_result(self, result: ToolResult) -> str:
        if result.status == "executed":
            return f"Tool result ({result.tool}): {result.data}"
        return f"Tool result ({result.tool}): {result.for_model()}"
