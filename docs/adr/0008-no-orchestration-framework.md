# ADR-0008 — Hand-written orchestrator, no agent framework in V1

## Status

Accepted.

## Context

`docs/11` forbids "one large AI prompt" and requires modular agents, but does not say
how the Executive Agent decides who handles a request. The obvious options are an
existing framework (LangChain, LangGraph, LlamaIndex, CrewAI) or writing the loop
ourselves. `docs/14` additionally states that Ray is a learning platform and that the
system should be understandable.

## Decision

**Write the orchestrator ourselves.** No agent framework in V1.

`ray/core/orchestrator.py` implements one explicit pipeline:

```
1. load conversation (short-term memory)
2. retrieve relevant long-term memories        -> ray/memory/retrieval.py
3. assemble context within a token budget      -> ray/core/context.py
4. Executive Agent selects target agent(s)     -> function-calling, one LLM call
5. run the selected agent, exposing its tools  -> ray/tools/manager.py
6. tool loop: execute, gate side effects, feed results back
7. Executive composes the final answer when more than one agent ran
8. persist message, memories, and agent activity
9. emit trace events throughout                -> ray/core/trace.py
```

Routing uses the provider's native function-calling: the Executive is given one
"delegate" function per enabled agent and picks. **Single-agent routing is the default.**
Multi-agent fan-out happens only when the Executive explicitly selects more than one
delegate, which keeps the common case to two LLM calls rather than five.

This is roughly 300 lines. It is directly readable, directly debuggable with a
breakpoint, and every step is a place to log a trace event for the HUD.

## Alternatives considered

* **LangGraph.** The best fit of the frameworks for stateful multi-agent flows, and it
  would save some plumbing. Rejected for V1 because it adds a large, fast-moving
  dependency whose abstractions would hide exactly the mechanics this project exists to
  teach, and because debugging a graph runtime is harder than debugging a for-loop.
  Reconsider if agent flows become genuinely cyclic and stateful.
* **LangChain.** Broadest ecosystem, but heavy, frequently API-breaking, and it
  encourages the tightly-coupled chains `docs/11` warns against.
* **Keyword/regex routing instead of an LLM router.** Free and instant, but brittle for
  natural requests like "help me get ready for Waterloo while finishing my game".
  Rejected — though a keyword fast-path for obvious cases is a valid later optimisation.

## Consequences

* We own retries, tool-loop termination (hard cap on tool iterations), and token
  budgeting. All three need tests.
* Provider differences in function calling must be normalised in the adapters
  (ADR-0001).
* Migrating to a framework later is contained: the orchestrator is one module behind one
  entry point.
