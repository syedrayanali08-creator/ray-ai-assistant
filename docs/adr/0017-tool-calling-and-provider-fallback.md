# ADR-0017: Tool Calling Abstraction and Provider Fallback

## Status

Accepted

## Context

Phase 4 adds agents that can call tools. Each model provider exposes function calling differently:

- Gemini uses a `tools` parameter and returns `function_call` parts.
- Ollama supports a `tools` parameter with OpenAI-style JSON schema.
- The local mock/deterministic provider has no model, so it cannot decide to call a tool on its own.

At the same time Ray must stay usable without a paid API key. If the preferred provider is unavailable or unconfigured, the system should fall back rather than fail.

## Decision

1. The provider abstraction (`ray.llm.base.LLMProvider`) carries tool specs and tool calls.
   - `CompletionRequest.tools` is a sequence of provider-neutral `ToolSpec` objects.
   - `Completion.tool_calls` is a tuple of `ToolCall` objects.
   - Providers that do not support function calling leave `tool_calls` empty; callers handle the absence.
2. The Tool Manager is the only place tool code runs.
   - Agents receive a `ToolInvoker` and may only call `specs()` and `call()`.
   - The manager enforces allow-lists, side-effect approval, and timeout.
3. When a provider is unavailable, the orchestrator records the degradation and tries the next provider in the chain.
   - `ProviderRegistry.chain()` always ends with `mock` so Ray can answer with no credentials.
   - A degraded provider is shown in the trace; it is not hidden.
4. The mock provider is intentionally not tool-aware.
   - It streams a canned response so the UI and conversation loop work without a model.
   - Keyword routing still chooses the right agent, and tests use a `FakeProvider` with deterministic `tool_routing` to exercise the tool loop.

## Consequences

- Adding a new provider only requires mapping `ToolSpec` and `ToolCall` to the vendor format.
- Agents never import the database or an integration client; the `ToolInvoker` seam keeps prompt-injection risks away from credentials.
- Tool support degrades gracefully: a missing key or local model does not break chat, it just means the model cannot call tools and keyword routing takes over.
- The mock provider cannot demonstrate real tool use to end users; for that they need Gemini or Ollama.
