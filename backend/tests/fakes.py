"""Test doubles for the model layer.

Every test in the gate runs against these: CI must never call a real provider, both
because it costs a free-tier quota and because a non-deterministic dependency turns
a test suite into a weather report.
"""

from collections.abc import AsyncIterator

from ray.llm.base import (
    Chunk,
    Completion,
    CompletionRequest,
    LLMError,
    LLMProvider,
    ProviderInfo,
    ToolCall,
)


class FakeProvider(LLMProvider):
    """Yields scripted chunks, and optionally fails in a scripted way.

    ``tool_routing`` makes a request with ``tools`` return a deterministic
    ``ToolCall`` when the offered tools include the named one. This lets the
    orchestrator and agent tests exercise the tool loop without a real model.
    """

    def __init__(
        self,
        chunks: list[str] | None = None,
        *,
        name: str = "fake",
        fail_with: LLMError | None = None,
        fail_after_chunks: int | None = None,
        tool_routing: dict[str, dict[str, object]] | None = None,
    ) -> None:
        self.name = name
        self._chunks = chunks if chunks is not None else ["Hello", " there"]
        self._fail_with = fail_with
        self._fail_after = fail_after_chunks
        self._tool_routing = tool_routing or {}
        self.calls: list[CompletionRequest] = []

    async def complete(self, request: CompletionRequest) -> Completion:
        self.calls.append(request)
        if self._fail_with is not None:
            raise self._fail_with

        if request.tools:
            tool = next((t for t in request.tools if t.name in self._tool_routing), None)
            if tool is not None:
                return Completion(
                    text="",
                    provider=self.name,
                    model="fake",
                    tool_calls=(ToolCall(name=tool.name, arguments=self._tool_routing[tool.name]),),
                )

        return Completion(text="".join(self._chunks), provider=self.name, model="fake")

    async def stream(self, request: CompletionRequest) -> AsyncIterator[Chunk]:
        self.calls.append(request)
        if self._fail_with is not None and self._fail_after is None:
            raise self._fail_with
        for index, text in enumerate(self._chunks):
            if self._fail_with is not None and index == self._fail_after:
                raise self._fail_with
            yield Chunk(text=text)
        yield Chunk(is_final=True)

    def info(self) -> ProviderInfo:
        return ProviderInfo(name=self.name, model="fake", configured=True)
