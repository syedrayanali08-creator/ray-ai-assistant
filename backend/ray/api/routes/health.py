"""Health check — the only unauthenticated route (ADR-0006)."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ray.config import Settings, get_settings
from ray.db.session import get_session
from ray.schemas import HealthResponse, VoiceCapabilities
from ray.voice.manager import VoiceManager

router = APIRouter(tags=["health"])

VERSION = "0.1.0"


@router.get("/health", response_model=HealthResponse)
async def health(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    # A health check that does not touch the database tells you nothing useful.
    try:
        await session.execute(text("SELECT 1"))
        database = "connected"
    except Exception:
        database = "unavailable"

    caps = VoiceManager(settings).info()

    return HealthResponse(
        status="ok" if database == "connected" else "degraded",
        version=VERSION,
        database=database,
        llm_provider=settings.llm_provider,
        voice=VoiceCapabilities(
            stt_backend=caps.stt_backend,
            tts_backend=caps.tts_backend,
            wake_word_enabled=caps.wake_word_enabled,
            wake_words=caps.wake_words,
            local_ready=caps.local_ready,
            local_detail=caps.local_detail,
        ),
    )
