"""Adapter behaviour against mocked transports — never a live model."""

import json
from collections.abc import Callable

import httpx
import pytest

from ray.llm.base import (
    CompletionRequest,
    LLMMessage,
    ProviderUnavailableError,
    RateLimitedError,
)
from ray.llm.providers.ollama import OllamaProvider

REQUEST = CompletionRequest(messages=[LLMMessage(role="user", content="hi")], system="You are Ray.")


def _provider(handler: Callable[[httpx.Request], httpx.Response]) -> OllamaProvider:
    return OllamaProvider(
        host="http://ollama.test",
        model="llama3.2",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://ollama.test"
        ),
    )


async def test_ollama_maps_the_system_prompt_into_the_message_list() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "hello"}, "done": True})

    completion = await _provider(handler).complete(REQUEST)

    # Ollama has no separate system field; it must become the first message.
    assert captured["messages"] == [
        {"role": "system", "content": "You are Ray."},
        {"role": "user", "content": "hi"},
    ]
    assert captured["stream"] is False
    assert completion.text == "hello"
    assert completion.provider == "ollama"


async def test_ollama_streams_newline_delimited_json() -> None:
    lines = [
        json.dumps({"message": {"content": "one "}, "done": False}),
        "",  # Keep-alive blank lines appear in practice and must be ignored.
        json.dumps({"message": {"content": "two"}, "done": False}),
        json.dumps({"message": {"content": ""}, "done": True}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="\n".join(lines))

    chunks = [chunk async for chunk in _provider(handler).stream(REQUEST)]
    assert "".join(c.text for c in chunks) == "one two"
    assert chunks[-1].is_final


async def test_ollama_not_running_is_unavailable_not_a_crash() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(ProviderUnavailableError):
        await _provider(handler).complete(REQUEST)


async def test_ollama_missing_model_is_reported_as_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'llama3.2' not found"})

    with pytest.raises(ProviderUnavailableError):
        await _provider(handler).complete(REQUEST)


def test_ollama_describes_itself_without_being_called() -> None:
    info = OllamaProvider(host="http://ollama.test", model="llama3.2").info()
    assert info.name == "ollama"
    assert info.model == "llama3.2"


class TestGeminiMapping:
    """Request mapping is pure, so it is tested without touching the network."""

    def test_assistant_turns_become_the_model_role(self) -> None:
        from ray.llm.providers.gemini import _to_contents

        contents = _to_contents(
            CompletionRequest(
                messages=[
                    LLMMessage(role="user", content="hi"),
                    LLMMessage(role="assistant", content="hello"),
                ]
            )
        )
        assert [content.role for content in contents] == ["user", "model"]

    def test_system_prompt_is_config_not_a_turn(self) -> None:
        from ray.llm.providers.gemini import _to_config, _to_contents

        request = CompletionRequest(
            messages=[LLMMessage(role="user", content="hi")], system="You are Ray."
        )
        assert len(_to_contents(request)) == 1
        assert _to_config(request).system_instruction == "You are Ray."

    def test_quota_errors_become_retryable(self) -> None:
        from google.genai import errors as genai_errors

        from ray.llm.providers.gemini import _translate

        error = genai_errors.ClientError(429, {"error": {"message": "quota exceeded", "code": 429}})
        assert isinstance(_translate(error), RateLimitedError)

    def test_server_errors_are_retryable_elsewhere(self) -> None:
        from google.genai import errors as genai_errors

        from ray.llm.providers.gemini import _translate

        error = genai_errors.ServerError(503, {"error": {"message": "overloaded", "code": 503}})
        assert isinstance(_translate(error), ProviderUnavailableError)

    def test_unknown_model_falls_back_rather_than_failing_the_turn(self) -> None:
        from google.genai import errors as genai_errors

        from ray.llm.providers.gemini import _translate

        error = genai_errors.ClientError(404, {"error": {"message": "not found", "code": 404}})
        assert isinstance(_translate(error), ProviderUnavailableError)

    def test_gemini_advertises_tool_support(self) -> None:
        from ray.llm.providers.gemini import GeminiProvider

        provider = GeminiProvider("test-key", model="gemini-flash-latest")
        assert provider.supports_tools() is True
        assert provider.info().configured is True
