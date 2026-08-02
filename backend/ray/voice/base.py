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


class WakeWordDetector(ABC):
    """Detects the activation phrase.

    Runs client-side so microphone audio never leaves the machine before
    activation (docs/12).
    """

    @abstractmethod
    def listen(self) -> AsyncIterator[WakeEvent]: ...

    @abstractmethod
    async def stop(self) -> None: ...


class SpeechToText(ABC):
    @abstractmethod
    async def transcribe(self, audio: bytes, *, sample_rate: int = 16_000) -> Transcript: ...

    @abstractmethod
    def transcribe_stream(self, chunks: AsyncIterator[AudioChunk]) -> AsyncIterator[Transcript]:
        """Yield partial transcripts so the HUD can show words as they are spoken."""


class TextToSpeech(ABC):
    @abstractmethod
    def synthesize(self, request: SpeechRequest) -> AsyncIterator[AudioChunk]:
        """Stream audio so playback starts before the whole answer is rendered."""

    @abstractmethod
    async def available_voices(self) -> list[str]: ...
