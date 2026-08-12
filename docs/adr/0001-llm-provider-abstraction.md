# ADR-0001 — LLM provider abstraction with Gemini as the default

## Status

Accepted. Amended by [ADR-0015](0015-mock-provider-and-graceful-degradation.md), which
adds a `mock` provider as the final link in the fallback chain and defers the Groq
adapter to the phase that introduces routing.

## Context

`docs/11` requires that Ray is never hardcoded to one AI provider and that models can
be replaced later. `docs/01` requires that Ray costs nothing to run after development.
These two requirements interact badly if a single provider is chosen up front: free
tiers change terms, get rate limited, or disappear, and the strongest models are paid.

Ray also needs different qualities from the model at different moments. Intent routing
is a short, high-frequency, latency-sensitive call. A coding explanation is a long,
quality-sensitive call. Forcing both through one model wastes either quality or time.

## Decision

All model access goes through a narrow in-house interface, `ray.llm.base.LLMProvider`,
with three methods: `complete()`, `stream()`, and `supports_tools()`. Nothing outside
`ray/llm/` may import a vendor SDK.

Three adapters ship in V1:

* **`gemini`** — Google AI Studio free tier. **This is the default.** It has the most
  generous free tier of the credible options, native function calling (which the agent
  router depends on), and a long context window that suits memory-heavy prompts.
* **`groq`** — free tier, extremely low latency. Used for the routing/classification
  calls where speed matters more than depth.
* **`ollama`** — local models. Zero cost, zero rate limit, and nothing leaves the
  machine. This is the privacy and offline fallback, and it is what makes the
  "no paid services" requirement genuinely true rather than dependent on someone
  else's free tier.

Selection is per-role, not global, so the router and the agents can use different
models:

```
RAY_LLM_PROVIDER=gemini          # default for agent responses
RAY_LLM_ROUTER_PROVIDER=groq     # optional override for routing calls
RAY_LLM_FALLBACK_PROVIDER=ollama # used when the primary errors or rate limits
```

When the primary provider returns a rate-limit or availability error, the core retries
once against the fallback provider and records the degradation in the response trace so
the UI can say so. A failing provider degrades Ray; it does not break Ray.

Adding a paid provider later is a new file in `ray/llm/providers/` and an env var. No
other code changes.

## Alternatives considered

* **Pick one provider and move on.** Fastest to build, but directly violates `docs/11`
  and leaves Ray dead if the free tier changes.
* **Use LiteLLM or a similar universal client.** Covers many providers for free, but
  adds a large dependency whose abstraction is broader than Ray needs, and it obscures
  provider-specific tool-calling differences that Ray must handle explicitly. Our
  interface is roughly 80 lines; the dependency is not worth it. Revisit if the number
  of adapters grows past four.
* **Local-only from day one.** Best privacy and true zero cost, but the quality of an
  8B local model is not enough to make the Executive Agent's routing and the Coding
  Agent's teaching feel like Jarvis on the hardware available. Kept as the fallback.

## Consequences

* Personal data reaches Google when running on the default. This must be stated plainly
  in the README and in `docs/12`, and the user can switch to `ollama` at any time with
  one env var.
* Every adapter must normalise tool-call formats to one internal shape, which is real
  work in each adapter.
* Prompts must stay reasonably provider-neutral; provider-specific prompt hacks are not
  allowed outside the adapter layer.
