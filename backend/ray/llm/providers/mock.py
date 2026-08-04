"""A provider that needs nothing.

Ray must start and answer even with no API key and no local model running, because
a missing key is a configuration state rather than a crash. This adapter is also
what the test suite runs against, so CI never touches a network.
"""

import asyncio
from collections.abc import AsyncIterator

from ray.llm.base import (
    Chunk,
    Completion,
    CompletionRequest,
    LLMProvider,
    ProviderInfo,
)

_PREFIX = (
    "I'm running on the mock provider, so this reply is canned rather than "
    "generated. Set RAY_GEMINI_API_KEY or start Ollama to get a real answer. "
    "You asked: "
)


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self, *, delay_seconds: float = 0.0) -> None:
        # A small delay makes the streaming UI visibly stream during development.
        self._delay = delay_seconds

    def _reply(self, request: CompletionRequest) -> str:
        last_user = next(
            (m.content for m in reversed(request.messages) if m.role == "user"),
            "",
        )
        return f"{_PREFIX}{last_user}"

    async def complete(self, request: CompletionRequest) -> Completion:
        return Completion(text=self._reply(request), provider=self.name, model="mock")

    async def stream(self, request: CompletionRequest) -> AsyncIterator[Chunk]:
        # Word by word, so consumers exercise the same accumulation path as a real
        # provider rather than receiving one big chunk.
        words = self._reply(request).split(" ")
        for index, word in enumerate(words):
            if self._delay:
                await asyncio.sleep(self._delay)
            suffix = "" if index == len(words) - 1 else " "
            yield Chunk(text=f"{word}{suffix}")
        yield Chunk(is_final=True)

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            model="mock",
            configured=True,
            detail="Canned responses; no model is being called.",
        )
