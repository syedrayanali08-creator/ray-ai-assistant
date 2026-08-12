"""What an agent is (ADR-0005).

An agent is a class with a prompt and a ``run`` method that yields events. It never
touches the database or an integration directly — the context it needs is handed to
it, and anything it wants to *do* goes through the Tool Manager in Phase 4. The
import-linter contract enforces this rather than trusting the convention.
"""

import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

from ray.agents.registry import AgentSpec
from ray.domain.enums import Modality
from ray.llm.base import LLMMessage
from ray.memory.retrieval import RetrievedMemory

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    """Prompts are versioned files, so a prompt change is a reviewable diff."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


@dataclass
class AgentContext:
    """Everything an agent is allowed to know about the request."""

    user_id: uuid.UUID
    user_name: str
    message: str
    history: list[LLMMessage] = field(default_factory=list)
    memories: list[RetrievedMemory] = field(default_factory=list)
    output_modality: Modality = Modality.TEXT
    project_id: uuid.UUID | None = None


@dataclass(frozen=True)
class AgentToken:
    """A fragment of the answer, as it is produced."""

    text: str


@dataclass(frozen=True)
class AgentFinished:
    """The end of a turn.

    ``speech_text`` is a separate rendering rather than the markdown with the
    formatting stripped, because a good spoken answer is shorter and has no code
    (ADR-0009).
    """

    content: str
    speech_text: str


AgentEvent = AgentToken | AgentFinished


class Agent(ABC):
    spec: AgentSpec

    @abstractmethod
    def system_prompt(self, ctx: AgentContext) -> str: ...

    @abstractmethod
    def run(self, ctx: AgentContext) -> AsyncIterator[AgentEvent]: ...

    @property
    def name(self) -> str:
        return self.spec.name
