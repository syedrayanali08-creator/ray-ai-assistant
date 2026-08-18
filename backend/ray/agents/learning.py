"""Learning Agent — explains, quizzes, and tracks proficiency per topic."""

from ray.agents.base import AgentContext
from ray.agents.registry import get_agent_spec
from ray.agents.tool_agent import ToolUsingAgent
from ray.tools.types import ToolResult


class LearningAgent(ToolUsingAgent):
    spec = get_agent_spec("learning")
    prompt_name = "learning"

    def _render_tool_result(self, result: ToolResult) -> str:
        if result.status == "executed":
            return f"Tool result ({result.tool}): {result.data}"
        return f"Tool result ({result.tool}): {result.for_model()}"

    def system_prompt(self, ctx: AgentContext) -> str:
        prompt = super().system_prompt(ctx)
        # Ask the agent to request the user's record by topic if the topic is clear,
        # rather than guess. The tool result will then select the explanation mode.
        prompt += (
            "\n\n## Teaching mode\n\n"
            "Before explaining a topic, call learning.get for it. If the user's "
            "proficiency is beginner, explain the concept and ask them to try it; do "
            "not dump a complete solution. If advanced, discuss tradeoffs and "
            "architecture, skip fundamentals."
        )
        return prompt
