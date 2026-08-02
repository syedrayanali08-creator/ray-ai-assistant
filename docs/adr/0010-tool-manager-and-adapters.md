# ADR-0010 — Tool Manager with swappable integration adapters

## Status

Accepted.

## Context

`docs/04` requires that agents never talk to external services directly and that
everything goes through a Tool Manager. It also lists integrations without ranking their
cost or difficulty, implying they are equivalent — they are not. GitHub has a free,
well-documented API. Google Calendar needs an OAuth app and a Cloud project. Notion is a
free cloud API. Obsidian has *no* API at all; it is a folder of markdown files.

## Decision

### Three layers, strictly separated

```
Agent  →  Tool Manager  →  Adapter (interface)  →  Integration (concrete client)
```

* **Tool** — what an agent sees: a name, a JSON schema, a description, and a
  `side_effect: bool` flag. Agents only ever see tools.
* **Tool Manager** (`ray/tools/manager.py`) — owns the registry, per-tool permissions,
  credential injection, the approval gate (ADR-0014), timeouts, error normalisation,
  and activity logging. Every tool call in Ray goes through exactly one function here.
* **Adapter** — a capability interface, e.g. `CalendarAdapter` with
  `list_events / create_event / update_event / delete_event`.
* **Integration** — a concrete implementation of an adapter: `LocalCalendar`,
  `GoogleCalendar`, `ICSCalendar`. Swapping providers is a config change, and the agent
  is unaware.

Adapters exist for **calendar** and **knowledge** (the two places where multiple
providers realistically compete). GitHub and the file system get a single
implementation each — inventing an adapter interface for one implementation is
speculative generality.

### Integration priority and V1 scope

| # | Integration | V1 scope | Notes |
|---|---|---|---|
| 1 | **GitHub** | Read-only: repo tree, file contents, commits, issues | Free API, PAT auth, no OAuth app needed. Highest value for the Coding Agent. Write access (issues/PRs) is post-V1 and gated by ADR-0014. |
| 2 | **Calendar** | `LocalCalendar` (own table) is the default; ICS import/export | Google Calendar is an **opt-in** integration behind the same adapter, because it requires a Google Cloud project and OAuth consent, which conflicts with "easy setup" in `docs/13`. |
| 3 | **Knowledge (Obsidian first)** | `ObsidianVault`: read, create, and link notes in a local vault directory | Chosen over Notion for V1 because it is local, free, needs no auth, and doubles as durable storage for Ray's own research output. `NotionKnowledge` is the second implementation of the same adapter, optional. |
| 4 | **Local files** | Read and summarise within explicitly allow-listed directories | Never unrestricted; the allow-list is user configuration, per `docs/04`. |

### Failure behaviour

Adapters raise typed errors (`IntegrationAuthError`, `IntegrationUnavailableError`,
`IntegrationRateLimited`). The Tool Manager converts them to a structured result the
agent can reason about and the UI can display, matching the error shape in `docs/08`.
A broken integration produces "GitHub auth expired — reconnect in Settings", never a
silent failure or a hallucinated answer. This is the foundation of the self-repair
behaviour in `docs/04`.

## Alternatives considered

* **Agents call integration clients directly.** Less indirection, but breaks the
  explicit rule in `docs/04` and scatters auth, permissions, and error handling across
  every agent.
* **Adapter interfaces for everything including GitHub.** Symmetric, but there is no
  second code-hosting provider on the roadmap. Add the interface when the second
  implementation appears.
* **Notion before Obsidian.** Notion has a real API and is easier than it looks, but it
  is a cloud dependency for data that can just be local files.

## Consequences

* Every new integration is: adapter (if needed) + integration + tool registration +
  permission entry + settings UI row. Predictable and repeatable.
* Credentials are held by the Tool Manager, injected at call time, and never passed into
  an agent's context — so a prompt injection cannot exfiltrate a token.
* Tool schemas are the contract with the LLM and must stay small and unambiguous;
  overly broad tools produce bad tool calls.
