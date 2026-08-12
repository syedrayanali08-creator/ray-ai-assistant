"""Server-sent event framing (ADR-0007).

One place decides how an orchestrator event becomes bytes on the wire, so the
client's parser has exactly one format to trust.
"""

import json
from dataclasses import asdict
from typing import Any

from ray.core.events import StreamEvent


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    # UUIDs and datetimes both stringify to something the client can use.
    return str(value)


def format_event(event: StreamEvent) -> str:
    """Render one event as an SSE frame.

    The event name is carried in the ``event:`` field *and* in the payload: the
    former is what an SSE parser dispatches on, the latter survives logging and
    replay of the raw JSON.
    """
    payload = _jsonable(asdict(event))
    name = payload["event"]
    data = json.dumps(payload, separators=(",", ":"))
    return f"event: {name}\ndata: {data}\n\n"


# Streaming only works if nothing between Ray and the browser buffers it.
SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
