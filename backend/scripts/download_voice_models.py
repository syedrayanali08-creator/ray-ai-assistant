"""Download the optional local voice model files.

Usage:
    uv run python scripts/download_voice_models.py
    uv run python scripts/download_voice_models.py --voice en_US-lessac-low --stt-model tiny

The script downloads a Piper voice model and pre-loads the faster-whisper STT model so
both are cached before Ray starts.
"""

import argparse
import os
import urllib.request
from pathlib import Path

DEFAULT_VOICE = "en_US-lessac-low"
DEFAULT_STT_MODEL = "tiny"


def _voice_url_parts(voice: str) -> tuple[str, str, str, str]:
    """Turn 'en_US-lessac-low' -> ('en', 'en_US', 'lessac', 'low')."""
    parts = voice.split("-")
    if len(parts) != 3:
        raise ValueError(f"voice must match '<region>-<name>-<quality>' (e.g. {DEFAULT_VOICE})")
    region, name, quality = parts
    family = region.split("_")[0]
    return family, region, name, quality


def _download(url: str, destination: Path) -> None:
    if destination.exists() and destination.stat().st_size > 0:
        print(f"  already exists: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {destination.name} ...")
    with urllib.request.urlopen(url) as response, open(destination, "wb") as f:
        while True:
            chunk = response.read(8192)
            if not chunk:
                break
            f.write(chunk)
    print(f"  saved {destination} ({destination.stat().st_size} bytes)")


def _download_piper_voice(directory: Path, voice: str) -> None:
    family, region, name, quality = _voice_url_parts(voice)
    base_url = (
        f"https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
        f"{family}/{region}/{name}/{quality}/{voice}"
    )
    model_path = directory / f"{voice}.onnx"
    config_path = directory / f"{voice}.onnx.json"
    _download(f"{base_url}.onnx?download=true", model_path)
    _download(f"{base_url}.onnx.json?download=true", config_path)


def _preload_stt(model_name: str) -> None:
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:  # pragma: no cover
        print(
            "  skipping STT preload: faster-whisper is not installed "
            f"({exc}). Run: uv sync --group voice"
        )
        return
    print(f"  preloading faster-whisper model '{model_name}' (first run may be slow) ...")
    WhisperModel(model_name, device="cpu", compute_type="int8")
    print("  STT model cached")


def _preload_tts(directory: Path, voice: str) -> None:
    try:
        from piper import PiperVoice
    except Exception as exc:  # pragma: no cover
        print(
            "  skipping TTS preload: piper-tts is not installed "
            f"({exc}). Run: uv sync --group voice"
        )
        return
    model_path = directory / f"{voice}.onnx"
    if not model_path.exists():
        print("  skipping TTS preload: model file not found")
        return
    print(f"  preloading Piper voice from {model_path} ...")
    PiperVoice.load(str(model_path))
    print("  TTS voice loaded")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download local voice model files")
    parser.add_argument(
        "--dir",
        default=os.environ.get("RAY_VOICE_MODELS_DIR", "~/.local/share/ray/voices"),
        help="Directory to download voice models into (default: ~/.local/share/ray/voices)",
    )
    parser.add_argument(
        "--voice",
        default=DEFAULT_VOICE,
        help=f"Piper voice to download (default: {DEFAULT_VOICE})",
    )
    parser.add_argument(
        "--stt-model",
        default=DEFAULT_STT_MODEL,
        help=f"faster-whisper model size to preload (default: {DEFAULT_STT_MODEL})",
    )
    parser.add_argument(
        "--skip-stt",
        action="store_true",
        help="Do not preload the faster-whisper model",
    )
    parser.add_argument(
        "--skip-tts-preload",
        action="store_true",
        help="Do not load the Piper voice after downloading",
    )
    args = parser.parse_args()

    directory = Path(os.path.expanduser(args.dir)).resolve()
    print(f"Voice models directory: {directory}")

    print("Downloading Piper voice ...")
    _download_piper_voice(directory, args.voice)

    if not args.skip_tts_preload:
        _preload_tts(directory, args.voice)

    if not args.skip_stt:
        _preload_stt(args.stt_model)

    print("\nAdd these to your .env to use the local voice stack:")
    print(f"  RAY_VOICE_MODELS_DIR={directory}")
    print("  RAY_STT_BACKEND=local")
    print("  RAY_TTS_BACKEND=local")
    print(f"  RAY_TTS_VOICE={args.voice}.onnx")
    print("  # Optional: enable server-side wake-word keyword spotting")
    print("  # RAY_WAKE_WORD_ENABLED=true")


if __name__ == "__main__":
    main()
