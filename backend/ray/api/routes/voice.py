"""Voice WebSocket endpoint (ADR-0009).

The local voice pipeline is the one place in Ray where audio bytes move. Everything
before activation is either handled by the browser (with browser backends) or by the
local backend; in either case no audio reaches a cloud provider.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ray.config import get_settings
from ray.voice.manager import get_voice_manager

router = APIRouter(tags=["voice"])

# Starlette WebSocket close codes; fastapi.status does not re-export all of them.
WS_CLOSE_POLICY = 1008
WS_CLOSE_SERVER_ERROR = 1011


def _token_from_query(websocket: WebSocket) -> str | None:
    return websocket.query_params.get("token")


def _verify_token(token: str | None) -> bool:
    if token is None:
        return False
    return token == get_settings().api_token


@router.websocket("/voice/stream")
async def voice_stream(websocket: WebSocket) -> None:
    token = _token_from_query(websocket)
    if not _verify_token(token):
        await websocket.close(code=WS_CLOSE_POLICY)
        return

    manager = get_voice_manager()
    caps = manager.info()
    if not caps.local_ready and manager.settings.stt_backend == "local":
        await websocket.close(
            code=WS_CLOSE_SERVER_ERROR,
            reason=caps.local_detail or "local voice is not ready",
        )
        return

    # One user per local install; resolve to the seeded user.
    from ray.db.session import get_sessionmaker
    from ray.services import user_service

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        first_user = await user_service.get_first_user(session)

    if first_user is None:
        await websocket.close(
            code=WS_CLOSE_SERVER_ERROR,
            reason="No user has been seeded. Run: uv run python scripts/seed.py",
        )
        return

    session_obj = await manager.session(first_user.id)
    try:
        await session_obj.run(websocket)
    except WebSocketDisconnect:
        pass
