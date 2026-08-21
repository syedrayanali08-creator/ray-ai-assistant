"""The Executive Agent.

In Phase 2 it answered everything directly. In Phase 4 it either answers directly,
routes to a specialist, or composes the output of multiple specialists into one
streaming answer (ADR-0008).

In Phase 8 it becomes a tool-using agent so it can capture user feedback as a task,
search memory, and keep the final response streaming.
"""

import json
from collections.abc import AsyncIterator, Callable
from dataclasses import asdict, dataclass

from ray.agents.base import AgentContext, AgentEvent, AgentFinished, AgentToken
from ray.agents.registry import get_agent_spec
from ray.agents.speech import to_speech
from ray.agents.tool_agent import ToolUsingAgent
from ray.llm.base import CompletionRequest, LLMMessage
from ray.llm.registry import Degradation, ProviderRegistry
from ray.tools.types import ToolResult


@dataclass
class ExecutiveAgent(ToolUsingAgent):
    """Routes, answers directly, and composes specialist outputs."""

    spec = get_agent_spec("executive")

    def __init__(
        self,
        providers: ProviderRegistry,
        *,
        temperature: float = 0.7,
        on_degrade: Callable[[Degradation], None] | None = None,
    ) -> None:
        super().__init__(providers, temperature=temperature, on_degrade=on_degrade)

    @property
    def prompt_name(self) -> str:
        return "executive"

    def _render_tool_result(self, result: ToolResult) -> str:
        return f"Tool result for {result.tool}: {json.dumps(asdict(result), default=str)}"

    async def compose(
        self,
        ctx: AgentContext,
        outputs: list[dict[str, str]],
    ) -> AsyncIterator[AgentEvent]:
        """Combine several specialist answers into one coherent streaming answer."""
        parts = "\n\n".join(f"### {out['agent']}\n{out['content']}" for out in outputs)
        messages = [
            *ctx.history,
            LLMMessage(role="user", content=ctx.message),
            LLMMessage(role="assistant", content=parts),
            LLMMessage(
                role="user",
                content=(
                    "Combine the above specialist notes into one concise answer. "
                    "Do not mention the specialists unless their input is surprising. "
                    "Lead with the answer."
                ),
            ),
        ]
        request = CompletionRequest(
            messages=messages,
            system=self.system_prompt(ctx),
            temperature=self._temperature,
        )

        content_parts: list[str] = []
        async for chunk in self._providers.stream(request, on_degrade=self._on_degrade):
            if chunk.text:
                content_parts.append(chunk.text)
                yield AgentToken(text=chunk.text)

        content = "".join(content_parts)
        yield AgentFinished(content=content, speech_text=to_speech(content))
