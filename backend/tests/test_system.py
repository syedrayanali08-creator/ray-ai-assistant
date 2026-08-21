"""System-level self-diagnosis and data export (Phase 8)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_diagnostics_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/system/diagnostics")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_diagnostics_reports_database_and_user(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/system/diagnostics")
    assert response.status_code == 200
    data = response.json()
    assert data["checks"]["database"] == "ok"
    assert "llm" in data["checks"]
    assert "voice" in data["checks"]
    assert "integrations" in data["checks"]
    assert "user" in data["checks"]
    assert data["overall"] in ("ok", "needs_attention")
    assert isinstance(data["suggestions"], list)


@pytest.mark.asyncio
async def test_export_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/system/export")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_export_returns_complete_user_snapshot(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/system/export")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "exported_at" in data
    assert data["user"]["name"] == "Test User"
    assert isinstance(data["memories"], list)
    assert isinstance(data["projects"], list)
    assert isinstance(data["tasks"], list)
    assert isinstance(data["events"], list)
    assert isinstance(data["integrations"], list)
    assert isinstance(data["tool_permissions"], list)
    assert isinstance(data["conversations"], list)
