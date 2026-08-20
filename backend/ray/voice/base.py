"""Voice interfaces (ADR-0009).

Ray is voice-first, so these contracts exist from Phase 1 even though the
implementations arrive later. Defining them now is what stops voice from becoming
a retrofit: the core pipeline is already modality-aware, and adding faster-whisper
in Phase 6 means writing one class, not reshaping the request path.

Phase 2 adds browser-backed implementations, Phase 6 local ones, Phase 6b the wake
word.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class WakeEvent:
    """Emitted the moment "Ray" is detected."""

    phrase: str
    confidence: float
    detected_at: datetime


@dataclass(frozen=True)
class Transcript:
    text: str
    confidence: float
    language: str = "en"
    duration_seconds: float | None = None
    is_final: bool = True


@dataclass(frozen=True)
class AudioChunk:
    data: bytes
    sample_rate: int = 16_000
    is_final: bool = False


@dataclass
class SpeechRequest:
    """A response on its way to the speaker.

    ``text`` is the spoken variant, not the markdown one — read a code block aloud
    and the experience collapses.
    """

    text: str
    voice: str = "default"
    speed: float = 1.0
    metadata: dict[str, str] = field(default_factory=dict)


class VoiceError(Exception):
    """A voice operation cannot proceed."""


class VoiceProviderInfo:
    """Whether a local voice component is ready and, if not, why."""

    def __init__(self, name: str, ready: bool, detail: str = "") -> None:
        self.name = name
        self.ready = ready
        self.detail = detail


class WakeWordDetector(ABC):
    """Detects the activation phrase.

    The default implementation runs in the browser, but the same interface is
    reused server-side for openWakeWord in Phase 6. Audio never leaves the
    machine in either case (docs/12).
    """

    @abstractmethod
    async def feed(self, audio: bytes, *, sample_rate: int = 16_000) -> WakeEvent | None: ...

    @abstractmethod
    async def reset(self) -> None: ...

    @abstractmethod
    def info(self) -> VoiceProviderInfo: ...


class SpeechToText(ABC):
    @abstractmethod
    async def transcribe(self, audio: bytes, *, sample_rate: int = 16_000) -> Transcript: ...

    @abstractmethod
    async def transcribe_stream(
        self, chunks: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[Transcript]:
        """Yield partial transcripts so the HUD can show words as they are spoken."""

    @abstractmethod
    def info(self) -> VoiceProviderInfo: ...


class TextToSpeech(ABC):
    @abstractmethod
    async def synthesize(self, request: SpeechRequest) -> AsyncIterator[AudioChunk]:
        """Stream audio so playback starts before the whole answer is rendered."""

    @abstractmethod
    async def available_voices(self) -> list[str]: ...

    @abstractmethod
    def info(self) -> VoiceProviderInfo: ...
