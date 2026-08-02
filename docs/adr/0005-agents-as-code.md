# ADR-0005 — Agents are code modules, not database rows

## Status

Accepted. Clarifies the `Agent` table in `docs/06`.

## Context

`docs/03` specifies agents as modules with a purpose, instructions, tools, memory access
rules, and limitations. `docs/06` separately defined an `Agent` table holding `name`,
`description`, `enabled`, and `configuration`. Read literally, this puts agent
behaviour — including prompts — in the database, where it is not versioned, not code
reviewed, not testable in CI, and not reproducible from a fresh clone.

## Decision

**An agent is a Python class.** Behaviour lives entirely in code:

```
ray/agents/
├── base.py        # Agent ABC: name, purpose, instructions, tools,
│                  # memory_scopes, limitations, handle(context) -> AgentResult
├── registry.py    # name -> Agent instance; the Executive routes against this
├── executive.py   planning.py   coding.py   learning.py   research.py
└── prompts/       # versioned prompt templates, reviewed like code
```

Prompts are files in `agents/prompts/`, so a prompt change is a reviewable diff.

**The Memory system is a service, not an agent.** `docs/03` listed a "Memory Agent", but
memory retrieval happens on every single request and must be deterministic and fast;
routing it through an LLM turn would add latency and non-determinism to the hot path.
Memory therefore lives in `ray/memory/` as a service that the core always calls, and it
is additionally exposed to agents as a *tool* (`memory.search`, `memory.write`) for the
cases where an agent needs to look something up mid-reasoning. This keeps every
capability `docs/03` asked for while removing an unnecessary LLM hop.

**The database stores runtime state only:**

* `agent_configs` — `agent_name`, `enabled`, `user_overrides` (JSONB), `updated_at`.
  Lets the user disable an agent or tweak preferences from Settings without a redeploy.
* `agent_activity` — `agent_name`, `action`, `tools_used`, `result_summary`, `duration_ms`,
  `conversation_id`, `created_at`. This is what powers the transparency requirement in
  `docs/12` and the agent visualization in `docs/09`.

There is no foreign key from activity to an agent row; `agent_name` is the code-side
identifier. An agent that no longer exists still has readable history.

## Alternatives considered

* **Agents fully in the database**, as the original schema implied — configurable at
  runtime, but unversioned and untestable. Rejected.
* **Agents as separate microservices.** Genuinely swappable and independently
  deployable, but wildly over-engineered for a single-user local assistant and adds
  network hops to every request. Rejected per the "do not over-engineer" instruction.

## Consequences

* Adding an agent means adding a file and registering it — and, per `docs/03`, must not
  require modifying any existing agent.
* Enabling/disabling agents at runtime is supported; changing their *behaviour* at
  runtime is deliberately not.
* Prompt changes are testable: the eval set (`docs/15`) runs against them in CI.
