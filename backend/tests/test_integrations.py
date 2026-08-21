"""Phase 5 integration tests: adapters, services, routes, and tools."""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ray.agents.registry import AGENTS
from ray.domain.enums import IntegrationStatus, IntegrationType
from ray.integrations.files import LocalFileAdapter
from ray.integrations.github import GitHubAdapter
from ray.integrations.knowledge import ObsidianAdapter
from ray.schemas import (
    CalendarEventCreate,
    IntegrationCreate,
    IntegrationUpdate,
    ProjectCreate,
    ProjectUpdate,
)
from ray.services import calendar_service, integration_service, project_service
from ray.tools.integration_tools import INTEGRATION_TOOLS
from ray.tools.manager import ToolContext, ToolManager, get_manager

# ---------------------------------------------------------------------------
# GitHub adapter
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, json_data: object) -> None:
        self.status_code = status_code
        self._json = json_data

    def json(self) -> object:
        return self._json


@pytest.fixture
def github_requests() -> list[tuple[str, dict[str, str] | None]]:
    return []


@pytest.fixture
def patched_github(monkeypatch, github_requests: list) -> None:
    async def _get(self, url, **kwargs):
        github_requests.append((url, kwargs.get("headers")))
        if "contents" in url:
            content = base64.b64encode(b"hello from github").decode()
            return _FakeResponse(200, {"content": content, "path": "README.md", "sha": "abc"})
        if "issues" in url:
            return _FakeResponse(
                200,
                [
                    {
                        "number": 1,
                        "title": "bug",
                        "state": "open",
                        "labels": [{"name": "triage"}],
                        "body": "bug body",
                    }
                ],
            )
        if "commits" in url:
            return _FakeResponse(
                200,
                [
                    {
                        "sha": "1234567890abcdef",
                        "commit": {
                            "message": "first commit\nmore lines",
                            "author": {"name": "Ray", "date": "2026-08-01T00:00:00Z"},
                        },
                    }
                ],
            )
        if "git/trees" in url:
            return _FakeResponse(200, {"tree": [{"path": "README.md", "type": "blob", "size": 19}]})
        return _FakeResponse(200, {"full_name": "owner/repo", "description": "test repo"})

    monkeypatch.setattr(httpx.AsyncClient, "get", _get)


@pytest.mark.asyncio
async def test_github_no_token_reports_clear_error(monkeypatch) -> None:
    monkeypatch.delenv("RAY_GITHUB_TOKEN", raising=False)
    adapter = GitHubAdapter()
    result = await adapter.check()
    assert not result.ok
    assert "token" in result.error.lower()


@pytest.mark.asyncio
async def test_github_request_mapping(patched_github, github_requests: list) -> None:
    adapter = GitHubAdapter(token="fake-token")

    await adapter.get_repo("owner/repo")
    assert github_requests[-1][0] == "https://api.github.com/repos/owner/repo"

    await adapter.get_tree("owner/repo")
    assert "git/trees" in github_requests[-1][0]
    assert "recursive=1" in github_requests[-1][0]

    await adapter.get_file("owner/repo", path="README.md")
    assert "contents/README.md" in github_requests[-1][0]

    await adapter.get_issues("owner/repo")
    assert "issues?state=open" in github_requests[-1][0]

    await adapter.get_commits("owner/repo")
    assert "commits?per_page=10" in github_requests[-1][0]


@pytest.mark.asyncio
async def test_github_decodes_base64_file(patched_github) -> None:
    adapter = GitHubAdapter(token="fake-token")
    result = await adapter.get_file("owner/repo", path="README.md")
    assert result.ok
    assert result.data["content"] == "hello from github"


@pytest.mark.asyncio
async def test_github_normalises_http_errors(patched_github, monkeypatch) -> None:
    async def _get(self, url, **kwargs):
        return _FakeResponse(404, {"message": "Not Found"})

    monkeypatch.setattr(httpx.AsyncClient, "get", _get)
    adapter = GitHubAdapter(token="fake-token")
    result = await adapter.get_repo("owner/missing")
    assert not result.ok
    assert result.error == "Not Found"


@pytest.mark.asyncio
async def test_github_network_failure_is_explainable(monkeypatch) -> None:
    async def _get(self, url, **kwargs):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(httpx.AsyncClient, "get", _get)
    adapter = GitHubAdapter(token="fake-token")
    result = await adapter.get_repo("owner/repo")
    assert not result.ok
    assert "network" in result.error.lower() or "github request failed" in result.error.lower()


# ---------------------------------------------------------------------------
# Obsidian / knowledge adapter
# ---------------------------------------------------------------------------


@pytest.fixture
def obsidian_vault(tmp_path) -> str:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "notes").mkdir()
    (vault / "notes" / "ideas.md").write_text("# Ideas\n\nBuild Ray.")
    (vault / "todo.md").write_text("# Todo\n\n- test obsidian")
    return str(vault)


@pytest.mark.asyncio
async def test_obsidian_search_finds_notes(obsidian_vault: str) -> None:
    adapter = ObsidianAdapter(vault_path=obsidian_vault)
    result = await adapter.search("ray")
    assert result.ok
    matches = result.data["matches"]
    assert len(matches) == 1
    assert matches[0]["path"].endswith("ideas.md")


@pytest.mark.asyncio
async def test_obsidian_blocks_traversal_outside_vault(obsidian_vault: str) -> None:
    adapter = ObsidianAdapter(vault_path=obsidian_vault)
    result = await adapter.get_note("../outside.md")
    assert not result.ok
    assert "outside" in result.error.lower()


# ---------------------------------------------------------------------------
# Local file adapter
# ---------------------------------------------------------------------------


@pytest.fixture
def allowed_root(tmp_path) -> str:
    root = tmp_path / "allowed"
    root.mkdir()
    (root / "hello.txt").write_text("hello world")
    (root / "binary.bin").write_bytes(b"\x00\x01\x02")
    return str(root)


@pytest.mark.asyncio
async def test_local_file_reads_text(allowed_root: str) -> None:
    adapter = LocalFileAdapter(allowed_paths=[allowed_root])
    result = await adapter.read("hello.txt")
    assert result.ok
    assert result.data["content"] == "hello world"


@pytest.mark.asyncio
async def test_local_file_refuses_binary(allowed_root: str) -> None:
    adapter = LocalFileAdapter(allowed_paths=[allowed_root])
    result = await adapter.read("binary.bin")
    assert not result.ok
    assert "binary" in result.error.lower()


@pytest.mark.asyncio
async def test_local_file_blocks_outside_allow_list(allowed_root: str) -> None:
    adapter = LocalFileAdapter(allowed_paths=[allowed_root])
    result = await adapter.read("../outside.txt")
    assert not result.ok
    assert "allow-list" in result.error.lower() or "outside" in result.error.lower()


# ---------------------------------------------------------------------------
# Calendar / ICS
# ---------------------------------------------------------------------------


def test_ics_export_import_round_trip() -> None:
    now = datetime.now(UTC)
    event = CalendarEventCreate(
        title="Sprint planning",
        start_time=now,
        end_time=now + timedelta(hours=1),
        description="Plan the sprint.",
        location="Office",
    )
    ics = calendar_service.export_ics([])
    assert "VCALENDAR" in ics
    assert "VEVENT" not in ics

    from ray.schemas import CalendarEventRead

    read_event = CalendarEventRead(
        id=uuid.uuid4(),
        title=event.title,
        description=event.description,
        start_time=event.start_time,
        end_time=event.end_time,
        location=event.location,
        source="ray",
        external_id=None,
        task_id=None,
    )
    ics = calendar_service.export_ics([read_event])
    assert "Sprint planning" in ics
    assert "VEVENT" in ics

    imported = calendar_service.import_ics(ics)
    assert len(imported) == 1
    assert imported[0].title == "Sprint planning"
    assert imported[0].location == "Office"


# ---------------------------------------------------------------------------
# Integration service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_crud_and_health_check(session: AsyncSession, user) -> None:
    user_id = user.id
    created = await integration_service.create_integration(
        session,
        user_id,
        IntegrationCreate(
            type=IntegrationType.FILES,
            provider="local",
            enabled=False,
            config={"allowed_paths": ["/tmp"]},
        ),
    )
    assert created.provider == "local"
    assert not created.enabled
    assert created.status == IntegrationStatus.DISCONNECTED

    # Expose safe fields only: references are OK, raw secret values are not.
    json_out = created.model_dump_json().lower()
    assert '"credentials":' not in json_out
    assert "api_key" not in json_out
    assert "token" not in json_out
    assert created.credentials_reference is None

    updated = await integration_service.update_integration(
        session,
        user_id,
        created.id,
        IntegrationUpdate(enabled=True),
    )
    assert updated is not None
    assert updated.enabled is True

    check = await integration_service.check_integration(session, user_id, created.id)
    assert check is not None
    assert check.ok
    assert check.message == "Connected."

    listed = await integration_service.list_integrations(session, user_id)
    assert len(listed) == 1

    deleted = await integration_service.delete_integration(session, user_id, created.id)
    assert deleted is True
    assert await integration_service.get_integration(session, user_id, created.id) is None


@pytest.mark.asyncio
async def test_integration_adapter_resolution(session: AsyncSession, user) -> None:
    await integration_service.create_integration(
        session,
        user.id,
        IntegrationCreate(
            type=IntegrationType.KNOWLEDGE,
            provider="obsidian",
            enabled=True,
            config={"vault_path": "/tmp"},
        ),
    )
    adapter = await integration_service.resolve_adapter(
        session, user.id, IntegrationType.KNOWLEDGE, "obsidian"
    )
    assert isinstance(adapter, ObsidianAdapter)


# ---------------------------------------------------------------------------
# Project / calendar service and routes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_project_crud_and_progress(session: AsyncSession, user) -> None:
    project = await project_service.create_project(
        session,
        user.id,
        ProjectCreate(name="Starfall Sprint", repo_url="https://github.com/owner/repo"),
    )
    assert project.name == "Starfall Sprint"

    updated = await project_service.update_project(
        session, user.id, project.id, ProjectUpdate(progress=75)
    )
    assert updated is not None
    assert updated.progress == 75

    fetched = await project_service.get_project(session, user.id, project.id)
    assert fetched is not None
    assert fetched.repo_url == "https://github.com/owner/repo"

    deleted = await project_service.delete_project(session, user.id, project.id)
    assert deleted is True


@pytest.mark.asyncio
async def test_calendar_rejects_invalid_time_range(session: AsyncSession, user) -> None:
    now = datetime.now(UTC)
    with pytest.raises(calendar_service.InvalidEventError):
        await calendar_service.create_event(
            session,
            user.id,
            CalendarEventCreate(
                title="Bad event", start_time=now, end_time=now - timedelta(hours=1)
            ),
        )


@pytest.mark.asyncio
async def test_project_api_crud(auth_client) -> None:
    resp = await auth_client.post(
        "/projects",
        json={"name": "Starfall Sprint", "description": "Phase 5"},
    )
    assert resp.status_code == 201
    body = resp.json()
    project_id = body["id"]
    assert body["name"] == "Starfall Sprint"

    resp = await auth_client.get(f"/projects/{project_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Starfall Sprint"

    resp = await auth_client.patch(f"/projects/{project_id}", json={"progress": 60})
    assert resp.status_code == 200
    assert resp.json()["progress"] == 60

    resp = await auth_client.delete(f"/projects/{project_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_calendar_api_ics_round_trip(auth_client) -> None:
    start = datetime.now(UTC) + timedelta(days=1)
    end = start + timedelta(hours=1)
    resp = await auth_client.post(
        "/calendar/event",
        json={"title": "Demo", "start_time": start.isoformat(), "end_time": end.isoformat()},
    )
    assert resp.status_code == 201

    resp = await auth_client.get("/calendar/export.ics")
    assert resp.status_code == 200
    ics = resp.text
    assert "BEGIN:VCALENDAR" in ics
    assert "Demo" in ics

    resp = await auth_client.post(
        "/calendar/import.ics",
        content=ics,
        headers={"content-type": "text/calendar"},
    )
    assert resp.status_code == 201
    assert len(resp.json()) == 1


# ---------------------------------------------------------------------------
# Tool Manager / agent allow-lists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integration_tools_are_registered(session: AsyncSession, user) -> None:
    manager = ToolManager()
    for tool in INTEGRATION_TOOLS:
        manager.register(tool)
    for name in (
        "github.read_repo",
        "github.read_tree",
        "github.read_file",
        "github.read_issues",
        "github.read_commits",
        "files.read",
        "knowledge.search",
        "knowledge.read",
        "calendar.ics_export",
        "calendar.ics_import",
    ):
        assert manager.get(name) is not None


@pytest.mark.asyncio
async def test_coding_agent_has_github_tools() -> None:
    coding = AGENTS["coding"]
    assert "github.read_repo" in coding.tools
    assert "github.read_file" in coding.tools


@pytest.mark.asyncio
async def test_calendar_create_requires_approval(session: AsyncSession, user) -> None:
    manager = get_manager()
    ctx = ToolContext(session=session, user_id=user.id)
    start = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    end = (datetime.now(UTC) + timedelta(days=1, hours=1)).isoformat()
    result = await manager.invoke(
        ctx,
        "calendar.create",
        {"title": "Meeting", "start_time": start, "end_time": end},
        allowed=("calendar.create",),
    )
    assert result.status == "pending_approval"


@pytest.mark.asyncio
async def test_read_only_integration_does_not_require_approval(
    session: AsyncSession, user, monkeypatch
) -> None:
    async def _get(self, url, **kwargs):
        return _FakeResponse(200, {"full_name": "owner/repo"})

    monkeypatch.setattr(httpx.AsyncClient, "get", _get)
    monkeypatch.setenv("RAY_GITHUB_TOKEN", "fake-token")

    manager = get_manager()
    ctx = ToolContext(session=session, user_id=user.id)
    result = await manager.invoke(
        ctx,
        "github.read_repo",
        {"repo": "owner/repo"},
        allowed=("github.read_repo",),
    )
    assert result.status == "executed"
    assert result.data["full_name"] == "owner/repo"
