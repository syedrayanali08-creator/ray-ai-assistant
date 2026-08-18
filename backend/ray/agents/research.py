"""Research Agent — structured investigation that ends in an actionable plan.

In Phase 4 this agent is limited to the internal tools plus a deterministic local
fallback; web search and file integrations arrive in Phase 5.
"""

from ray.agents.registry import get_agent_spec
from ray.agents.tool_agent import ToolUsingAgent
from ray.tools.types import ToolResult


class ResearchAgent(ToolUsingAgent):
    spec = get_agent_spec("research")
    prompt_name = "research"

    def _render_tool_result(self, result: ToolResult) -> str:
        if result.status == "executed":
            return f"Tool result ({result.tool}): {result.data}"
        return f"Tool result ({result.tool}): {result.for_model()}"
