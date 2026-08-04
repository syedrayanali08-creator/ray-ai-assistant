"""The event vocabulary of a streamed turn (ADR-0007).

All six event types are defined now even though Phase 2 emits four: the frontend's
handler is written once, and Phase 4's tool calls and Phase 5's approval cards
arrive without a protocol change.
"""

import uuid
from dataclasses import dataclass, field
from typing import Literal

from ray.core.contracts import TraceStage


@dataclass(frozen=True)
class TraceStreamEvent:
    """A pipeline step that has just happened. Recorded by the code that did it."""

    stage: TraceStage
    detail: dict[str, object] = field(default_factory=dict)
    event: Literal["trace"] = "trace"


@dataclass(frozen=True)
class TokenEvent:
    text: str
    event: Literal["token"] = "token"


@dataclass(frozen=True)
class ToolStreamEvent:
    """Reserved for Phase 4. Defined here so the client handles it from day one."""

    tool: str
    status: Literal["running", "completed", "failed"]
    event: Literal["tool"] = "tool"


@dataclass(frozen=True)
class ApprovalEvent:
    """Reserved for Phase 5 (ADR-0014): a side-effecting call awaiting consent."""

    invocation_id: uuid.UUID
    tool: str
    payload: dict[str, object]
    event: Literal["approval"] = "approval"


@dataclass(frozen=True)
class ErrorEvent:
    """Mid-stream failure. Delivered as an event, not an HTTP status — the status
    line was already sent when the stream opened."""

    message: str
    retryable: bool = False
    event: Literal["error"] = "error"


@dataclass(frozen=True)
class DoneEvent:
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    agent_name: str
    speech_text: str
    duration_ms: int
    event: Literal["done"] = "done"


StreamEvent = (
    TraceStreamEvent | TokenEvent | ToolStreamEvent | ApprovalEvent | ErrorEvent | DoneEvent
)
