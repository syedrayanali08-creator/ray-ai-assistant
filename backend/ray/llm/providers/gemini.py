"""Google AI Studio adapter — Ray's default (ADR-0001).

The key is read from the environment and never logged. Absence of a key is not an
error here: the provider reports itself unconfigured and the registry picks the
fallback.
"""

from collections.abc import AsyncIterator

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from ray.llm.base import (
    Chunk,
    Completion,
    CompletionRequest,
    LLMProvider,
    ProviderInfo,
    ProviderRequestError,
    ProviderUnavailableError,
    RateLimitedError,
)

# The alias, not a pinned version: pinned free-tier models get their quota
# retired, and an alias keeps working when that happens.
DEFAULT_MODEL = "gemini-flash-latest"

# Gemini calls the assistant "model"; every other provider we support does not.
_ROLE_MAP = {"user": "user", "assistant": "model"}


def _to_contents(request: CompletionRequest) -> list[types.Content]:
    return [
        types.Content(
            role=_ROLE_MAP.get(message.role, "user"),
            parts=[types.Part.from_text(text=message.content)],
        )
        for message in request.messages
        if message.role != "system"
    ]


def _to_config(request: CompletionRequest) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=request.system or None,
        temperature=request.temperature,
        max_output_tokens=request.max_output_tokens,
    )


def _translate(exc: genai_errors.APIError) -> Exception:
    """Map vendor errors onto Ray's retryable/not-retryable distinction."""
    status = exc.code or 0
    if status == 429:
        return RateLimitedError(str(exc), provider="gemini")
    # 404 means the configured model does not exist for this key. That is a
    # configuration problem, and the useful response is the same as for an outage:
    # answer from the fallback instead of failing the turn.
    if status in (404, 503) or status >= 500 or status == 0:
        return ProviderUnavailableError(str(exc), provider="gemini")
    return ProviderRequestError(str(exc), provider="gemini")


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, *, model: str = DEFAULT_MODEL) -> None:
        self._model = model
        self._client = genai.Client(api_key=api_key)

    async def complete(self, request: CompletionRequest) -> Completion:
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=_to_contents(request),
                config=_to_config(request),
            )
        except genai_errors.APIError as exc:
            raise _translate(exc) from exc

        usage = response.usage_metadata
        return Completion(
            text=response.text or "",
            provider=self.name,
            model=self._model,
            input_tokens=usage.prompt_token_count if usage else None,
            output_tokens=usage.candidates_token_count if usage else None,
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[Chunk]:
        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=self._model,
                contents=_to_contents(request),
                config=_to_config(request),
            )
            async for event in stream:
                if event.text:
                    yield Chunk(text=event.text)
        except genai_errors.APIError as exc:
            raise _translate(exc) from exc
        yield Chunk(is_final=True)

    def info(self) -> ProviderInfo:
        return ProviderInfo(name=self.name, model=self._model, configured=True)

    def supports_tools(self) -> bool:
        return True
