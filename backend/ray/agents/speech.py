"""Spoken answer formatting shared across agents (ADR-0009)."""

import re

SPEECH_BUDGET_WORDS = 90

_CODE_FENCE = re.compile(r"```[\s\S]*?```")
_LINK = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
_BULLET = re.compile(r"^[-*+]+\s+", re.MULTILINE)
_MARKER = re.compile(r"[*#`_~]+")


def to_speech(content: str) -> str:
    """Return a short, speakable version of a markdown answer.

    Code blocks are replaced with a pointer, formatting characters are stripped, and
    anything longer than ``SPEECH_BUDGET_WORDS`` is summarised so local TTS has a
    bounded amount of audio to generate.
    """
    text = _strip_markdown(content)
    words = text.split()
    if len(words) <= SPEECH_BUDGET_WORDS:
        return text
    truncated = words[:SPEECH_BUDGET_WORDS]
    return " ".join(truncated) + " The rest is on screen."


def _strip_markdown(text: str) -> str:
    """Remove code fences, inline code, links, bullets, and heading/emphasis markers."""
    text = _CODE_FENCE.sub(" The code is on screen. ", text)
    text = _LINK.sub(r"\1", text)
    text = _BULLET.sub("", text)
    text = _MARKER.sub("", text)
    text = text.replace("\n", " ")
    return " ".join(text.split())
