"""The chat endpoint: SSE framing, persistence, and the auth boundary."""

import json
import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ray.api.routes.chat import get_orchestrator
from ray.config import Settings
from ray.core.orchestrator import Orchestrator
from ray.db.models import User
from ray.llm.base import RateLimitedError
from ray.llm.registry import ProviderRegistry
from ray.main import create_app
from tests.fakes import FakeProvider


def _parse_sse(body: str) -> list[tuple[str, dict[str, object]]]:
    """Parse the wire format the browser will parse, rather than trusting ours."""
    events: list[tuple[str, dict[str, object]]] = []
    for frame in body.split("\n\n"):
        if not frame.strip():
            continue
        lines = frame.split("\n")
        name = next(line[len("event: ") :] for line in lines if line.startswith("event: "))
        data = next(line[len("data: ") :] for line in lines if line.startswith("data: "))
        events.append((name, json.loads(data)))
    return events


@pytest.fixture
def chat_provider() -> FakeProvider:
    return FakeProvider(["Hello ", "Rayan"])


def _override(app: FastAPI, provider: FakeProvider) -> None:
    """Point the endpoint at a scripted provider instead of a real model."""
    settings = Settings(llm_provider="mock", llm_fallback_provider=None)
    registry = ProviderRegistry(settings)
    registry.register("mock", provider)
    app.dependency_overrides[get_orchestrator] = lambda: Orchestrator(
        providers=registry, settings=settings
    )


@pytest.fixture
def chat_app(chat_provider: FakeProvider) -> FastAPI:
    app = create_app()
    _override(app, chat_provider)
    return app


@pytest.fixture
async def chat_client(user: User, chat_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=chat_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.headers["Authorization"] = "Bearer test-token"
        yield client


async def test_message_streams_typed_sse_events(chat_client: AsyncClient) -> None:
    response = await chat_client.post("/chat/message", json={"message": "hi"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    # Nothing between Ray and the browser may buffer the stream.
    assert response.headers["x-accel-buffering"] == "no"

    events = _parse_sse(response.text)
    names = [name for name, _ in events]
    assert names[0] == "trace"
    assert "token" in names
    assert names[-1] == "done"
    assert "".join(str(p["text"]) for n, p in events if n == "token") == "Hello Rayan"


async def test_done_event_carries_the_ids_the_client_needs(chat_client: AsyncClient) -> None:
    events = _parse_sse((await chat_client.post("/chat/message", json={"message": "hi"})).text)
    _, done = events[-1]
    assert uuid.UUID(str(done["conversation_id"]))
    assert uuid.UUID(str(done["message_id"]))
    assert done["agent_name"] == "executive"
    assert done["speech_text"] == "Hello Rayan"


async def test_conversation_is_readable_afterwards(chat_client: AsyncClient) -> None:
    _, done = _parse_sse(
        (await chat_client.post("/chat/message", json={"message": "what is ray"})).text
    )[-1]

    history = (await chat_client.get("/chat/history")).json()
    assert len(history) == 1
    assert history[0]["title"] == "what is ray"
    assert history[0]["message_count"] == 2

    conversation = (await chat_client.get(f"/chat/{done['conversation_id']}")).json()
    assert [m["role"] for m in conversation["messages"]] == ["user", "assistant"]
    assert conversation["messages"][1]["trace"] is not None


async def test_continuing_a_conversation_does_not_create_a_second_one(
    chat_client: AsyncClient,
) -> None:
    _, first = _parse_sse((await chat_client.post("/chat/message", json={"message": "a"})).text)[-1]
    await chat_client.post(
        "/chat/message", json={"message": "b", "conversation_id": first["conversation_id"]}
    )
    assert len((await chat_client.get("/chat/history")).json()) == 1


async def test_provider_failure_is_reported_in_band(
    chat_app: FastAPI, chat_client: AsyncClient
) -> None:
    """The HTTP status is long gone by the time a provider fails."""
    _override(chat_app, FakeProvider(fail_with=RateLimitedError("quota", provider="gemini")))

    response = await chat_client.post("/chat/message", json={"message": "hi"})
    assert response.status_code == 200
    name, payload = _parse_sse(response.text)[-1]
    assert name == "error"
    assert payload["retryable"] is True


async def test_deleting_a_conversation_removes_its_messages(chat_client: AsyncClient) -> None:
    _, done = _parse_sse((await chat_client.post("/chat/message", json={"message": "hi"})).text)[-1]
    conversation_id = done["conversation_id"]

    assert (await chat_client.delete(f"/chat/{conversation_id}")).status_code == 204
    assert (await chat_client.get(f"/chat/{conversation_id}")).status_code == 404
    assert (await chat_client.delete(f"/chat/{conversation_id}")).status_code == 404


async def test_provider_status_lists_the_chain(chat_client: AsyncClient) -> None:
    providers = (await chat_client.get("/chat/providers")).json()

    assert providers[-1]["name"] == "mock", "mock always terminates the chain (ADR-0015)"
    assert all({"name", "model", "configured", "detail"} <= set(p) for p in providers)
    # An unconfigured provider explains itself by naming the variable to set, which
    # is the whole point of the endpoint.
    unconfigured = [p for p in providers if not p["configured"]]
    assert all(p["detail"] for p in unconfigured)


@pytest.mark.parametrize(
    "path,method",
    [
        ("/chat/message", "post"),
        ("/chat/history", "get"),
        ("/chat/providers", "get"),
        (f"/chat/{uuid.uuid4()}", "get"),
        (f"/chat/{uuid.uuid4()}", "delete"),
    ],
)
async def test_chat_routes_require_a_token(client: AsyncClient, path: str, method: str) -> None:
    response = await client.request(method, path, json={"message": "hi"})
    assert response.status_code == 401


async def test_empty_and_oversized_messages_are_rejected(chat_client: AsyncClient) -> None:
    assert (await chat_client.post("/chat/message", json={"message": ""})).status_code == 422
    long_message = "x" * 10_001
    assert (
        await chat_client.post("/chat/message", json={"message": long_message})
    ).status_code == 422


async def test_unknown_conversation_returns_404_not_someone_elses(
    chat_client: AsyncClient,
) -> None:
    assert (await chat_client.get(f"/chat/{uuid.uuid4()}")).status_code == 404
