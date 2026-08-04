"""Local models over Ollama's HTTP API (ADR-0001).

Deliberately no client library: the two endpoints Ray needs are a POST and a GET,
and ``httpx`` is already a dependency. This is the adapter that makes "no paid
services" true rather than dependent on someone else's free tier.
"""

import json
from collections.abc import AsyncIterator

import httpx

from ray.llm.base import (
    Chunk,
    Completion,
    CompletionRequest,
    LLMError,
    LLMProvider,
    ProviderInfo,
    ProviderRequestError,
    ProviderUnavailableError,
)

DEFAULT_MODEL = "llama3.2"
DEFAULT_HOST = "http://127.0.0.1:11434"


def _to_messages(request: CompletionRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if request.system:
        messages.append({"role": "system", "content": request.system})
    messages.extend({"role": m.role, "content": m.content} for m in request.messages)
    return messages


def _options(request: CompletionRequest) -> dict[str, object]:
    options: dict[str, object] = {"temperature": request.temperature}
    if request.max_output_tokens is not None:
        options["num_predict"] = request.max_output_tokens
    return options


def _translate_status(exc: httpx.HTTPStatusError) -> LLMError:
    """Map an Ollama HTTP status onto Ray's retryable/not-retryable distinction.

    A 404 means the model has not been pulled. That reads like a client error, but
    the useful response is the same as for a dead server: try the next provider.
    """
    status = exc.response.status_code
    if status in (404, 429) or status >= 500:
        return ProviderUnavailableError(exc.response.text, provider="ollama")
    return ProviderRequestError(exc.response.text, provider="ollama")


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(
        self,
        *,
        host: str = DEFAULT_HOST,
        model: str = DEFAULT_MODEL,
        timeout_seconds: float = 120.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._model = model
        self._host = host.rstrip("/")
        # Local generation on CPU is slow; a short timeout would fail perfectly
        # good requests.
        self._client = client or httpx.AsyncClient(base_url=self._host, timeout=timeout_seconds)

    async def complete(self, request: CompletionRequest) -> Completion:
        payload = {
            "model": self._model,
            "messages": _to_messages(request),
            "stream": False,
            "options": _options(request),
        }
        try:
            response = await self._client.post("/api/chat", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise _translate_status(exc) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(str(exc), provider=self.name) from exc

        body = response.json()
        return Completion(
            text=body.get("message", {}).get("content", ""),
            provider=self.name,
            model=self._model,
            input_tokens=body.get("prompt_eval_count"),
            output_tokens=body.get("eval_count"),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[Chunk]:
        payload = {
            "model": self._model,
            "messages": _to_messages(request),
            "stream": True,
            "options": _options(request),
        }
        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                # Ollama streams newline-delimited JSON, not SSE.
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    text = event.get("message", {}).get("content", "")
                    if text:
                        yield Chunk(text=text)
                    if event.get("done"):
                        break
        except httpx.HTTPStatusError as exc:
            raise ProviderRequestError(str(exc), provider=self.name) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(str(exc), provider=self.name) from exc
        yield Chunk(is_final=True)

    def info(self) -> ProviderInfo:
        return ProviderInfo(name=self.name, model=self._model, configured=True)

    async def aclose(self) -> None:
        await self._client.aclose()
