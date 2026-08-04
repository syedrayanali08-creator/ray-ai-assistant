# ADR-0015 — A mock provider terminates the fallback chain, and Groq is deferred

## Status

Accepted. Amends ADR-0001.

## Context

ADR-0001 established the provider abstraction and a per-role chain
(`primary → fallback`). Implementing it in Phase 2 exposed two things the original
decision did not settle.

**What happens when no provider is usable?** On a fresh clone there is no
`RAY_GEMINI_API_KEY` and no Ollama server. Under ADR-0001 as written, the first chat
message returns an error, which makes the very first minute of using Ray a failure.
Free tiers also make this a live concern rather than a hypothetical: the Gemini key
used during development returned `429 RESOURCE_EXHAUSTED` with `limit: 0`, and Ollama
is not installed on every machine Ray runs on.

**Groq.** ADR-0001 named three adapters, including Groq as the low-latency router
provider. But nothing in Phase 2 routes: there is one agent, and it answers every
message. A Groq adapter now would be an untested code path with a second API key to
manage, added for a caller that does not exist yet.

## Decision

**A `mock` provider is always the last link in the chain**, appended by the registry
rather than configured. It returns a canned, clearly-labelled answer that names the
environment variable to set. Ray therefore always starts, always answers, and always
explains itself; it is never a stack trace on first use.

**Failures are classified by whether a different provider could help**, not by
severity. `LLMError.is_retryable` drives the chain:

| Condition | Error | Retryable |
|---|---|---|
| No API key configured | `ProviderUnavailableError` | yes — skipped silently |
| Rate limited / quota exhausted | `RateLimitedError` | yes |
| Server error, connection refused | `ProviderUnavailableError` | yes |
| Model does not exist (404, either provider) | `ProviderUnavailableError` | yes |
| Malformed request (4xx) | `ProviderRequestError` | no |

A missing model is deliberately treated as an outage rather than a client error: it is
a configuration mistake, and answering from the fallback is more useful than failing
the turn.

**Fallback during streaming only happens before the first chunk.** Once the user has
seen tokens, switching providers would duplicate output; the stream fails with an
`error` event instead.

**Degradation is surfaced, not hidden.** Every fallback produces a `Degradation`, which
the orchestrator emits as a `trace` event, so the HUD can say the answer came from the
fallback and why.

**Groq is deferred** to the phase that introduces routing. `RAY_LLM_PROVIDER` accepts
`gemini | ollama | mock`; the `Settings` literal and the registry's `ProviderName` are
the same set, so a stale `RAY_LLM_ROUTER_PROVIDER=groq` fails loudly at startup instead
of silently doing nothing. Adding Groq later remains one file plus one env var, exactly
as ADR-0001 intended.

**`RAY_GEMINI_MODEL` defaults to the `gemini-flash-latest` alias** rather than a pinned
version, because pinned free-tier models have their quota retired.

## Alternatives considered

* **Fail loudly when nothing is configured.** Honest, and it is what a library should
  do. But Ray is a personal product, and "clone, run, get an error" is a worse first
  experience than "clone, run, get an answer that tells you what to configure".
* **Echo the input instead of a labelled canned reply.** Cheaper, but easy to mistake
  for a broken model. The mock says what it is in its first sentence.
* **Retry the same provider with backoff before falling back.** Correct for a transient
  blip, but a free-tier `429` usually means the quota is gone for the minute or the day.
  Falling back is faster and, with a local fallback, free. Revisit if the fallback is
  slow enough that a short retry would win.
* **Ship the Groq adapter now for completeness.** Rejected: untested code for an absent
  caller, plus a second secret to manage.

## Consequences

* A silently-degraded Ray is possible: a misconfigured key means mock answers. This is
  mitigated by the startup log line, `GET /chat/providers`, and the `trace` event — the
  degradation is visible in three places, and the mock answer names the cause.
* Tests run entirely against fakes and the mock provider. CI needs no API key and no
  network, which keeps it deterministic.
* `mock` is a real, supported provider name that can be set explicitly, which is how
  the frontend and evaluation suites get deterministic responses.
