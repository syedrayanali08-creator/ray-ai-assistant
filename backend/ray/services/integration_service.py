"""Integration service: manages adapter lifecycle and credentials.

Credentials are read from the environment variable or keyring reference stored in the
database; the database never contains the secret value (ADR-0010, docs/12).
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.models import Integration
from ray.domain.enums import IntegrationStatus, IntegrationType
from ray.integrations.base import Adapter
from ray.integrations.calendar import GoogleCalendarAdapter, LocalCalendarAdapter
from ray.integrations.files import LocalFileAdapter
from ray.integrations.github import GitHubAdapter
from ray.integrations.knowledge import NotionAdapter, ObsidianAdapter
from ray.schemas import (
    IntegrationCheck,
    IntegrationCreate,
    IntegrationRead,
    IntegrationUpdate,
)


@dataclass
class IntegrationAdapterConfig:
    """Database-free adapter recipe. Tools may pass this for fallbacks."""

    type: IntegrationType
    provider: str
    enabled: bool = True
    credentials_reference: str | None = None
    config: dict[str, Any] | None = None


_ADAPTER_MAP: dict[tuple[IntegrationType, str], Any] = {
    (IntegrationType.GITHUB, "github"): GitHubAdapter,
    (IntegrationType.CALENDAR, "local"): LocalCalendarAdapter,
    (IntegrationType.CALENDAR, "google"): GoogleCalendarAdapter,
    (IntegrationType.KNOWLEDGE, "obsidian"): ObsidianAdapter,
    (IntegrationType.KNOWLEDGE, "notion"): NotionAdapter,
    (IntegrationType.FILES, "local"): LocalFileAdapter,
}


def _resolve_credentials(reference: str | None) -> str | None:
    """Read the secret from an environment variable or keyring key.

    V1 supports environment variables only; keyring is future.
    """
    if not reference:
        return None
    if reference.startswith("env:"):
        return os.environ.get(reference[4:])
    return os.environ.get(reference)


def build_adapter(integration: Integration | IntegrationAdapterConfig) -> Adapter | None:
    """Construct an adapter instance from an integration or fallback config."""
    cls = _ADAPTER_MAP.get((integration.type, integration.provider))
    if cls is None:
        return None
    config = integration.config or {}
    cls_any = cast(Any, cls)
    if integration.type is IntegrationType.GITHUB:
        return cast(Adapter, cls_any(token=_resolve_credentials(integration.credentials_reference)))
    if integration.type is IntegrationType.KNOWLEDGE:
        if integration.provider == "notion":
            return cast(
                Adapter, cls_any(token=_resolve_credentials(integration.credentials_reference))
            )
        return cast(Adapter, cls_any(vault_path=config.get("vault_path")))
    if integration.type is IntegrationType.FILES:
        return cast(Adapter, cls_any(allowed_paths=config.get("allowed_paths", [])))
    if integration.type is IntegrationType.CALENDAR and integration.provider == "local":
        return cast(Adapter, cls_any())
    return cast(Adapter, cls_any())


async def list_integrations(session: AsyncSession, user_id: uuid.UUID) -> list[IntegrationRead]:
    result = await session.execute(
        select(Integration)
        .where(Integration.user_id == user_id)
        .order_by(Integration.type, Integration.provider)
    )
    return [IntegrationRead.model_validate(i) for i in result.scalars()]


async def get_integration(
    session: AsyncSession, user_id: uuid.UUID, integration_id: uuid.UUID
) -> IntegrationRead | None:
    stmt = select(Integration).where(
        Integration.id == integration_id, Integration.user_id == user_id
    )
    integration = (await session.execute(stmt)).scalar_one_or_none()
    return IntegrationRead.model_validate(integration) if integration else None


async def create_integration(
    session: AsyncSession, user_id: uuid.UUID, data: IntegrationCreate
) -> IntegrationRead:
    integration = Integration(user_id=user_id, **data.model_dump())
    # A new integration starts disconnected until checked.
    integration.status = IntegrationStatus.DISCONNECTED
    session.add(integration)
    await session.flush()
    return IntegrationRead.model_validate(integration)


async def update_integration(
    session: AsyncSession,
    user_id: uuid.UUID,
    integration_id: uuid.UUID,
    data: IntegrationUpdate,
) -> IntegrationRead | None:
    stmt = select(Integration).where(
        Integration.id == integration_id, Integration.user_id == user_id
    )
    integration = (await session.execute(stmt)).scalar_one_or_none()
    if integration is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(integration, field, value)
    await session.flush()
    await session.refresh(integration)
    return IntegrationRead.model_validate(integration)


async def delete_integration(
    session: AsyncSession, user_id: uuid.UUID, integration_id: uuid.UUID
) -> bool:
    stmt = select(Integration).where(
        Integration.id == integration_id, Integration.user_id == user_id
    )
    integration = (await session.execute(stmt)).scalar_one_or_none()
    if integration is None:
        return False
    await session.delete(integration)
    return True


async def check_integration(
    session: AsyncSession, user_id: uuid.UUID, integration_id: uuid.UUID
) -> IntegrationCheck | None:
    integration = (
        await session.execute(
            select(Integration).where(
                Integration.id == integration_id, Integration.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if integration is None:
        return None
    adapter = build_adapter(integration)
    if adapter is None:
        integration.status = IntegrationStatus.ERROR
        integration.last_error = f"No adapter for {integration.type}:{integration.provider}"
        await session.commit()
        return IntegrationCheck(ok=False, message=integration.last_error)
    result = await adapter.check()
    integration.status = IntegrationStatus.CONNECTED if result.ok else IntegrationStatus.ERROR
    integration.last_error = result.error if not result.ok else None
    if result.ok:
        integration.last_sync = datetime.now(UTC)
    await session.commit()
    return IntegrationCheck(ok=result.ok, message=result.error if not result.ok else "Connected.")


async def adapter_for(
    session: AsyncSession, user_id: uuid.UUID, integration_type: IntegrationType
) -> Any | None:
    """Return the first enabled, connected adapter of the given type."""
    result = await session.execute(
        select(Integration)
        .where(
            Integration.user_id == user_id,
            Integration.type == integration_type,
            Integration.enabled == True,  # noqa: E712
            Integration.status == IntegrationStatus.CONNECTED,
        )
        .order_by(Integration.created_at.asc())
    )
    integration = result.scalars().first()
    if integration is None:
        return None
    return build_adapter(integration)


async def resolve_adapter(
    session: AsyncSession,
    user_id: uuid.UUID,
    type: IntegrationType,
    provider: str,
    fallback: IntegrationAdapterConfig | None = None,
) -> Adapter | None:
    """Return the first enabled, connected adapter, or build a fallback config."""
    result = await session.execute(
        select(Integration)
        .where(
            Integration.user_id == user_id,
            Integration.type == type,
            Integration.provider == provider,
            Integration.enabled == True,  # noqa: E712
        )
        .order_by(Integration.created_at.asc())
    )
    integration = result.scalars().first()
    if integration is not None:
        return build_adapter(integration)
    if fallback is not None:
        return build_adapter(fallback)
    return None
