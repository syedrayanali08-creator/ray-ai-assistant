"""The Executive Agent.

In Phase 2 it answered everything directly. In Phase 4 it either answers directly,
routes to a specialist, or composes the output of multiple specialists into one
streaming answer (ADR-0008).
"""

from collections.abc import AsyncIterator, Callable

from ray.agents.base import Agent, AgentContext, AgentEvent, AgentFinished, AgentToken, load_prompt
from ray.agents.registry import get_agent_spec
from ray.domain.enums import Modality
from ray.llm.base import CompletionRequest, LLMMessage, StreamAccumulator
from ray.llm.registry import Degradation, ProviderRegistry

# A spoken answer is read aloud, so length is measured in patience rather than
# tokens. Anything longer than this gets a spoken summary instead.
SPEECH_BUDGET_WORDS = 90


class ExecutiveAgent(Agent):
    spec = get_agent_spec("executive")

    def __init__(
        self,
        providers: ProviderRegistry,
        *,
        temperature: float = 0.7,
        on_degrade: Callable[[Degradation], None] | None = None,
    ) -> None:
        self._providers = providers
        self._temperature = temperature
        self._on_degrade = on_degrade

    def system_prompt(self, ctx: AgentContext) -> str:
        prompt = load_prompt("executive").replace("{user_name}", ctx.user_name)
        if ctx.memories:
            remembered = "\n".join(f"- {m.content}" for m in ctx.memories)
            prompt += f"\n\n## What you remember about {ctx.user_name}\n\n{remembered}"
        if ctx.output_modality is Modality.VOICE:
            prompt += (
                "\n\n## This answer will be spoken aloud\n\n"
                "Keep it short and plain. No code blocks, no tables, no bullet lists, "
                "no markdown syntax — write it the way you would say it."
            )
        return prompt

    async def run(self, ctx: AgentContext) -> AsyncIterator[AgentEvent]:
        request = CompletionRequest(
            messages=[*ctx.history, LLMMessage(role="user", content=ctx.message)],
            system=self.system_prompt(ctx),
            temperature=self._temperature,
        )

        accumulator = StreamAccumulator()
        async for chunk in self._providers.stream(request, on_degrade=self._on_degrade):
            accumulator.add(chunk)
            if chunk.text:
                yield AgentToken(text=chunk.text)

        content = accumulator.text
        yield AgentFinished(content=content, speech_text=to_speech(content))

    def compose(
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

        accumulator = StreamAccumulator()

        async def _generator() -> AsyncIterator[AgentEvent]:
            async for chunk in self._providers.stream(request, on_degrade=self._on_degrade):
                accumulator.add(chunk)
                if chunk.text:
                    yield AgentToken(text=chunk.text)
            yield AgentFinished(content=accumulator.text, speech_text=to_speech(accumulator.text))

        return _generator()


def to_speech(content: str) -> str:
    """Best-effort spoken rendering of a written answer."""
    lines: list[str] = []
    in_code_block = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            if not in_code_block:
                lines.append("I've put the code on screen.")
            continue
        if in_code_block or stripped.startswith("|"):
            continue
        stripped = stripped.lstrip("#-*> ").replace("**", "").replace("`", "")
        if stripped:
            lines.append(stripped)

    spoken = " ".join(lines)
    words = spoken.split()
    if len(words) <= SPEECH_BUDGET_WORDS:
        return spoken

    truncated = " ".join(words[:SPEECH_BUDGET_WORDS])
    last_stop = max(truncated.rfind("."), truncated.rfind("?"), truncated.rfind("!"))
    if last_stop > 0:
        truncated = truncated[: last_stop + 1]
    return f"{truncated} The rest is on screen."
