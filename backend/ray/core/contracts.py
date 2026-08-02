"""The contract every request flows through.

Text is treated as a special case of the voice-capable path rather than the other
way around (ADR-0009): a request carries the modality it arrived in and the
modality it should leave in, and a response always carries both a screen form and
a spoken form.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from ray.domain.enums import Modality

TraceStage = Literal["routing", "memory", "agent", "tool", "compose"]


@dataclass(frozen=True)
class TraceEvent:
    """One observable step, streamed to the HUD as it happens (ADR-0007).

    docs/12 requires Ray to explain what it did; the trace is that explanation,
    recorded rather than narrated by the model.
    """

    stage: TraceStage
    detail: dict[str, object] = field(default_factory=dict)
    at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class RayRequest:
    user_id: uuid.UUID
    message: str
    conversation_id: uuid.UUID | None = None
    input_modality: Modality = Modality.TEXT
    output_modality: Modality = Modality.TEXT
    project_id: uuid.UUID | None = None


@dataclass
class RayResponse:
    """Both renderings of one answer.

    ``speech_text`` is generated alongside ``content`` rather than stripped from
    it, because a good spoken answer is a different answer: shorter, no code, no
    tables.
    """

    content: str
    speech_text: str
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    agent_name: str
    memories_used: list[uuid.UUID] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    trace: list[TraceEvent] = field(default_factory=list)
