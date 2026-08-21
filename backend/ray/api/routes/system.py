"""System-wide self-diagnosis and full data export (Phase 8)."""

import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ray.config import Settings, get_settings
from ray.db.session import get_session
from ray.llm.registry import get_registry
from ray.schemas import DiagnosticsResponse, ExportSnapshot, ToolPermissionRead
from ray.security.auth import get_current_user_id
from ray.services import (
    calendar_service,
    conversation_service,
    integration_service,
    memory_service,
    project_service,
    task_service,
    tool_service,
    user_service,
)
from ray.version import __version__
from ray.voice.manager import VoiceManager

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/diagnostics", response_model=DiagnosticsResponse)
async def diagnostics(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> DiagnosticsResponse:
    checks: dict[str, str] = {}
    suggestions: list[str] = []

    # Database.
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover - exercised by health check
        checks["database"] = "error"
        suggestions.append(f"Postgres is unreachable: {exc.__class__.__name__}")

    # LLM providers.
    configured = [p.name for p in get_registry().describe() if p.configured]
    if configured:
        checks["llm"] = f"ready ({', '.join(configured)})"
    else:
        checks["llm"] = "no provider configured"
        suggestions.append("Set RAY_GEMINI_API_KEY or start Ollama (RAY_OLLAMA_HOST).")

    # Voice.
    caps = VoiceManager(settings).info()
    if caps.local_ready:
        checks["voice"] = f"local ({caps.stt_backend} / {caps.tts_backend})"
    else:
        checks["voice"] = "browser fallback"
        suggestions.append(
            "Install the voice group and run scripts/download_voice_models.py for local STT/TTS."
        )

    # Integrations.
    integrations = await integration_service.list_integrations(session, user_id)
    failed = [i for i in integrations if i.status.value == "error"]
    checks["integrations"] = f"{len(integrations)} configured"
    if failed:
        checks["integrations"] += f", {len(failed)} error(s)"
        for i in failed:
            suggestions.append(f"Integration '{i.provider}' failed: {i.last_error or 'unknown'}")

    # Data ownership.
    user = await user_service.get_user(session, user_id)
    if user:
        checks["user"] = user.name
    else:
        checks["user"] = "missing"
        suggestions.append("No seeded user; restart the server so bootstrap creates one.")

    overall = "ok" if not suggestions and checks["database"] == "ok" else "needs_attention"
    return DiagnosticsResponse(overall=overall, checks=checks, suggestions=suggestions)


@router.get("/export", response_model=ExportSnapshot)
async def export_data(
    session: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ExportSnapshot:
    """Return a complete, user-owned snapshot of Ray data.

    Secrets are not included: ``credentials_reference`` is the *name* of an env var
    or keyring key, not the value (docs/12).
    """
    user = await user_service.get_user(session, user_id)
    if user is None:
        raise ValueError("User not found")

    memories = await memory_service.list_memories(session, user_id, limit=10000)
    projects = await project_service.list_projects(session, user_id)
    tasks = await task_service.list_tasks(session, user_id, include_done=True)
    events = await calendar_service.list_events(session, user_id, limit=10000)
    integrations = await integration_service.list_integrations(session, user_id)
    permissions = await tool_service.list_permissions(session, user_id)
    conversation_summaries = await conversation_service.list_conversations(
        session, user_id, limit=1000
    )

    conversations = await asyncio.gather(
        *[
            conversation_service.get_conversation(session, user_id, c.id)
            for c in conversation_summaries
        ]
    )

    tool_permissions = [
        ToolPermissionRead(tool_name=name, mode=mode) for name, mode in permissions.items()
    ]

    return ExportSnapshot(
        version=__version__,
        exported_at=datetime.now(UTC),
        user=user,
        memories=memories,
        projects=projects,
        tasks=tasks,
        events=events,
        integrations=integrations,
        tool_permissions=tool_permissions,
        conversations=[c for c in conversations if c is not None],
    )
