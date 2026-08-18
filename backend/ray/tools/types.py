"""What an agent knows about tools (ADR-0010).

Deliberately dependency-free. Agents may not import the database or an integration
client, and they may not import the Tool Manager either — they are handed something
that satisfies ``ToolInvoker`` and can only ask it to call a name with arguments.
Credentials, permissions, and the approval gate all live on the other side of this
seam, which is what makes a prompt injection unable to reach them (ADR-0014).
"""

import uuid
from dataclasses import dataclass, field
from typing import Literal, Protocol

from ray.llm.base import ToolSpec

ToolStatus = Literal["executed", "failed", "denied", "pending_approval"]


@dataclass(frozen=True)
class ToolResult:
    """The outcome of one tool call, in a form the model can reason about.

    A failure is a *result*, not an exception: "GitHub auth expired" is something Ray
    should say, and an agent that is told the call failed can explain itself instead
    of inventing an answer (ADR-0010).
    """

    tool: str
    status: ToolStatus
    data: dict[str, object] = field(default_factory=dict)
    error: str = ""
    # Set when the call is waiting on the user's approval, so the turn can show a card
    # and a later request can execute exactly this call.
    invocation_id: uuid.UUID | None = None

    @property
    def ok(self) -> bool:
        return self.status == "executed"

    def for_model(self) -> str:
        """How the result is written into the next prompt.

        Prose rather than raw JSON: the model reads it as an observation, and there is
        no ambiguity about whether the action already happened.
        """
        if self.status == "executed":
            return f"{self.tool} returned: {self.data}"
        if self.status == "pending_approval":
            return (
                f"{self.tool} is prepared but NOT done: it is waiting for "
                f"{self.data.get('summary', 'the user')} to be approved."
            )
        if self.status == "denied":
            return f"{self.tool} was not allowed: {self.error}"
        return f"{self.tool} failed: {self.error}"


class ToolInvoker(Protocol):
    """The only capability an agent has to affect the world."""

    def specs(self, allowed: tuple[str, ...]) -> list[ToolSpec]:
        """The tools this agent may use, as the model should see them."""
        ...

    async def call(
        self, name: str, arguments: dict[str, object], *, allowed: tuple[str, ...]
    ) -> ToolResult: ...


class NoTools:
    """An invoker that offers nothing.

    Used where an agent legitimately has no tools available — the mock provider path,
    unit tests of prompt construction — so ``ctx.tools`` is never ``None`` and no
    agent needs a special case for it.
    """

    def specs(self, allowed: tuple[str, ...]) -> list[ToolSpec]:
        return []

    async def call(
        self, name: str, arguments: dict[str, object], *, allowed: tuple[str, ...]
    ) -> ToolResult:
        return ToolResult(tool=name, status="denied", error="No tools are available.")
