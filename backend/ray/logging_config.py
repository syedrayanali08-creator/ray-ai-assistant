"""Structured logging and secret redaction (docs/12, docs/13).

Ray is a personal assistant: its logs are one of the places sensitive values can leak.
This module configures the whole process to emit JSON-ish logs and redact known secret
keys before they are written.
"""

from __future__ import annotations

import logging
import re
from collections.abc import MutableMapping
from typing import Any

import structlog

# Token-like patterns we never want in a log.
_SECRET_KEYS = re.compile(
    r"(.*(api[_-]?key|token|secret|password|credential|auth|bearer|private).*)",
    re.IGNORECASE,
)


def redact_secrets(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Mask values whose keys look like secrets, no matter how deeply nested."""
    event_dict["event"] = _redact_value(event_dict.get("event"))
    for key in list(event_dict.keys()):
        if key in ("event", "timestamp"):
            continue
        event_dict[key] = _redact_value(event_dict[key], key=key)
    return event_dict


def _redact_value(value: Any, key: str | None = None) -> Any:
    if key is not None and _SECRET_KEYS.search(key):
        return "[REDACTED]"
    if isinstance(value, MutableMapping):
        return {k: _redact_value(v, key=k) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    if isinstance(value, str) and _SECRET_KEYS.search(value):
        return "[REDACTED]"
    return value


def configure_logging(*, json: bool = False) -> None:
    """Set up structlog and stdlib logging once per process.

    JSON output is the default for production; development keeps human-readable logs.
    The application calls this in ``main.py`` lifespan, so tests keep plain output.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        redact_secrets,
    ]

    if json:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
        handlers=[logging.StreamHandler()],
    )
