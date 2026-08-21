"""Local voice providers: faster-whisper STT, Piper TTS, openWakeWord wake word.

These are optional installs. See ``pyproject.toml`` ``[dependency-groups] voice``
for the STT/TTS deps; openWakeWord must be installed manually because it is not
yet published with Python 3.12 wheels.

If a package or model file is missing the provider reports ``ready=False`` and an
explanatory ``detail`` string, so Ray still starts and the UI can fall back to
browser speech.
"""

import asyncio
import io
import os
import wave
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ray.voice.base import (
    AudioChunk,
    SpeechRequest,
    Transcript,
    VoiceError,
    VoiceProviderInfo,
    WakeEvent,
    WakeWordDetector,
)

# Optional heavy dependencies. They are only loaded when the user opts into the local
# voice stack; failing to import must not break the default install.
try:
    import numpy as np
except Exception:  # pragma: no cover - CI without the voice group
    np = None

try:
    from faster_whisper import WhisperModel
except Exception:  # pragma: no cover
    WhisperModel = None

try:
    from piper import PiperVoice
except Exception:  # pragma: no cover
    PiperVoice = None

try:
    from openwakeword.model import Model as OpenWakeWordModel
except Exception:  # pragma: no cover
    OpenWakeWordModel = None


class _Lazy:
    """Holds a lazily-initialised dependency so import failures surface as info, not crashes."""

    def __init__(self, factory: Any) -> None:
        self._factory = factory
        self._value: Any | None = None
        self._error: Exception | None = None

    def get(self) -> Any:
        if self._value is not None:
            return self._value
        if self._error is not None:
            raise self._error
        try:
            self._value = self._factory()
            return self._value
        except Exception as exc:  # pragma: no cover - exercised by missing models
            self._error = VoiceError(str(exc))
            raise self._error from exc


def _ensure_wav(audio: bytes, sample_rate: int) -> bytes:
    """Wrap raw 16-bit mono PCM in a WAV header, or pass through an existing WAV."""
    if audio.startswith(b"RIFF"):
        return audio
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio)
    return buffer.getvalue()


async def _ffmpeg_to_wav(audio: bytes) -> bytes:
    """Convert any audio ffmpeg understands to 16-bit 16 kHz mono WAV."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-i",
        "-",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-f",
        "wav",
        "-",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(input=audio)
    if proc.returncode != 0:
        raise VoiceError(f"ffmpeg failed: {stderr.decode(errors='ignore')[:200]}")
    return stdout


class LocalSpeechToText:
    """faster-whisper running on the local machine."""

    name = "local"

    def __init__(
        self,
        model_name: str = "tiny",
        language: str | None = None,
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_name = model_name
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self._model: _Lazy | None = None

    def _load(self) -> Any:
        if WhisperModel is None:
            raise VoiceError("faster-whisper is not installed. Run: uv sync --group voice")
        return WhisperModel(self.model_name, device=self.device, compute_type=self.compute_type)

    async def transcribe(self, audio: bytes, *, sample_rate: int = 16_000) -> Transcript:
        if not audio:
            return Transcript(text="", confidence=1.0, language="en")

        if self._model is None:
            self._model = _Lazy(self._load)
        model = await asyncio.to_thread(self._model.get)

        # Try a WAV header first; if the client sent raw WebM/MP3, ask ffmpeg to
        # normalise it. This keeps the WebSocket protocol simple: the client can
        # send whatever the browser microphone produces.
        try:
            audio_file = io.BytesIO(_ensure_wav(audio, sample_rate))
        except Exception:
            audio_file = io.BytesIO(await _ffmpeg_to_wav(audio))

        segments, info = await asyncio.to_thread(
            model.transcribe,
            audio_file,
            language=self.language,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        text = "".join(segment.text for segment in segments)
        return Transcript(
            text=text.strip(),
            confidence=1.0 - getattr(info, "no_speech_prob", 0.0),
            language=info.language or "en",
            duration_seconds=info.duration,
        )

    async def transcribe_stream(
        self, chunks: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[Transcript]:
        """faster-whisper is utterance-oriented; accumulate and transcribe at end."""
        buffer = bytearray()
        async for chunk in chunks:
            buffer.extend(chunk.data)
            if not chunk.is_final:
                # Keep the HUD alive while audio is still arriving.
                yield Transcript(text="", confidence=0.0, is_final=False)
            else:
                yield await self.transcribe(bytes(buffer))

    def info(self) -> VoiceProviderInfo:
        if WhisperModel is None:
            return VoiceProviderInfo("local_stt", False, "faster-whisper is not installed")
        if not self.model_name:
            return VoiceProviderInfo("local_stt", False, "stt_model is not configured")
        return VoiceProviderInfo("local_stt", True, f"model={self.model_name}")


class LocalTextToSpeech:
    """Piper local neural text-to-speech."""

    name = "local"

    def __init__(self, voice_path: str = "", length_scale: float = 1.0) -> None:
        self.voice_path = voice_path
        self.length_scale = length_scale
        self._voice: _Lazy | None = None

    def _load(self) -> Any:
        if PiperVoice is None:
            raise VoiceError("piper-tts is not installed. Run: uv sync --group voice")
        if not self.voice_path or not Path(self.voice_path).exists():
            raise VoiceError(f"Piper voice model not found: {self.voice_path}")
        return PiperVoice.load(self.voice_path)

    async def synthesize(self, request: SpeechRequest) -> AsyncIterator[AudioChunk]:
        if not request.text.strip():
            yield AudioChunk(data=b"", sample_rate=22_050, is_final=True)
            return

        if self._voice is None:
            self._voice = _Lazy(self._load)
        voice = await asyncio.to_thread(self._voice.get)

        def _stream() -> Iterator[AudioChunk]:
            for chunk in voice.synthesize(request.text, length_scale=self.length_scale):
                yield AudioChunk(
                    data=chunk.audio_int16_bytes,
                    sample_rate=chunk.sample_rate,
                    is_final=False,
                )
            yield AudioChunk(data=b"", sample_rate=22_050, is_final=True)

        # Piper is CPU-bound; run off the event loop.
        for audio_chunk in await asyncio.to_thread(list, _stream()):
            yield audio_chunk

    async def available_voices(self) -> list[str]:
        exists = await asyncio.to_thread(lambda: os.path.exists(self.voice_path))
        if self.voice_path and exists:
            return [self.voice_path]
        return []

    def info(self) -> VoiceProviderInfo:
        if PiperVoice is None:
            return VoiceProviderInfo("local_tts", False, "piper-tts is not installed")
        if not self.voice_path:
            return VoiceProviderInfo("local_tts", False, "tts_voice model path is not configured")
        if not Path(self.voice_path).exists():
            return VoiceProviderInfo(
                "local_tts", False, f"Piper voice model not found: {self.voice_path}"
            )
        return VoiceProviderInfo("local_tts", True, f"voice={Path(self.voice_path).name}")


class LocalWakeWord(WakeWordDetector):
    """openWakeWord running server-side for the local voice WebSocket."""

    name = "local"

    def __init__(self, model_path: str = "", keywords: list[str] | None = None) -> None:
        self.model_path = model_path
        self.keywords = [k.lower() for k in (keywords or ["ray", "jarvis"])]
        self._model: _Lazy | None = None
        self._last_detection: float = 0.0
        self._debounce_seconds = 1.0

    def _load(self) -> Any:
        if OpenWakeWordModel is None:
            raise VoiceError("openwakeword is not installed")
        if not self.model_path or not Path(self.model_path).exists():
            raise VoiceError(f"openWakeWord model not found: {self.model_path}")
        return OpenWakeWordModel(wakeword_models=[self.model_path])

    async def feed(self, audio: bytes, *, sample_rate: int = 16_000) -> WakeEvent | None:
        if not self.model_path:
            return None
        if np is None:
            raise VoiceError("numpy is not installed")

        if self._model is None:
            self._model = _Lazy(self._load)
        model = await asyncio.to_thread(self._model.get)

        expected_len = len(audio) // 2 * 2
        if expected_len == 0:
            return None
        frame = np.frombuffer(audio[:expected_len], dtype=np.int16)

        def _predict() -> Any:
            return model.predict(frame)

        predictions = await asyncio.to_thread(_predict)

        matched: tuple[str, float] | None = None
        for key, score in predictions.items():
            key_lower = str(key).lower()
            for keyword in self.keywords:
                if keyword in key_lower and float(score) > 0.5:
                    if matched is None or float(score) > matched[1]:
                        matched = (keyword, float(score))
            if matched is None and float(score) > 0.7:
                matched = (self.keywords[0], float(score))

        if matched is None:
            return None

        now = datetime.now(UTC).timestamp()
        if now - self._last_detection < self._debounce_seconds:
            return None
        self._last_detection = now
        return WakeEvent(phrase=matched[0], confidence=matched[1], detected_at=datetime.now(UTC))

    async def reset(self) -> None:
        if self._model is not None:
            try:
                model = await asyncio.to_thread(self._model.get)
                await asyncio.to_thread(model.reset)
            except Exception:
                pass

    def info(self) -> VoiceProviderInfo:
        if OpenWakeWordModel is None:
            return VoiceProviderInfo("local_wake", False, "openwakeword is not installed")
        if not self.model_path:
            return VoiceProviderInfo("local_wake", False, "wake_word_model path is not configured")
        if not Path(self.model_path).exists():
            return VoiceProviderInfo(
                "local_wake", False, f"openWakeWord model not found: {self.model_path}"
            )
        return VoiceProviderInfo("local_wake", True, f"model={Path(self.model_path).name}")
