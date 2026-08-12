"""The Executive Agent.

In Phase 2 it runs in single-agent mode: it answers everything itself. Phase 4 gives
it the routing decision it is named for, at which point this class gains a
``route()`` step and delegates — the rest of the pipeline does not change.
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


def to_speech(content: str) -> str:
    """Best-effort spoken rendering of a written answer.

    Voice output is a placeholder in Phase 2, so this is deliberately mechanical
    rather than a second model call: strip the syntax that has no spoken form, and
    stop at a sentence boundary once the answer gets long. Phase 6 replaces it with
    a purpose-generated spoken variant.
    """
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
        # Bullets and headings read badly aloud; keep the words, drop the markers.
        stripped = stripped.lstrip("#-*> ").replace("**", "").replace("`", "")
        if stripped:
            lines.append(stripped)

    spoken = " ".join(lines)
    words = spoken.split()
    if len(words) <= SPEECH_BUDGET_WORDS:
        return spoken

    truncated = " ".join(words[:SPEECH_BUDGET_WORDS])
    # Prefer ending on a sentence rather than mid-clause.
    last_stop = max(truncated.rfind("."), truncated.rfind("?"), truncated.rfind("!"))
    if last_stop > 0:
        truncated = truncated[: last_stop + 1]
    return f"{truncated} The rest is on screen."
