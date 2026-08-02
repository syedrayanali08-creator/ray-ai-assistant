# ADR-0014 — Explicit user approval for side-effecting tool calls

## Status

Accepted.

## Context

`docs/12` requires that calendar events are created "after user approval", that file
access is permissioned, and that GitHub write access is enabled only when necessary.
`docs/04` describes Ray applying changes only after approval. But no mechanism was
specified, and approval was treated as a per-integration concern rather than a system
property.

Ray also reads untrusted content — repository files, notes, web pages. That content can
contain instructions aimed at the model. Prompt injection is not a hypothetical risk for
an assistant with calendar, file, and repository access.

## Decision

**Every tool declares `side_effect: bool`. The Tool Manager physically cannot execute a
side-effecting tool without a recorded approval.**

Flow:

1. An agent requests a side-effecting tool call.
2. The Tool Manager creates a `tool_invocations` row with status `pending_approval` and
   emits an `approval` SSE event carrying the tool name and the exact payload.
3. The UI renders an approval card in the conversation showing precisely what will
   happen — "Create event *Coding block*, Tue 19:00–21:00" — with Approve and Reject.
4. On approval the call executes and the result is fed back into the agent loop; on
   rejection the agent is told it was rejected and continues without it.
5. The outcome is written to `agent_activity` either way.

**Read-only tools execute freely.** Requiring approval to read a task list would make
Ray useless. The gate exists for state change, not for thinking.

**Standing approvals** are supported to keep this from becoming click fatigue: the user
can grant "always allow `calendar.create_event`" from the approval card or Settings,
stored per-tool in `tool_permissions`. Standing approvals are revocable, are shown in
Settings, and are **never** available for tools that write outside Ray's own database
(GitHub writes, file writes) — those always ask.

**Prompt-injection containment**, layered on top:

* Content fetched from external sources is inserted into the prompt inside explicit
  untrusted-content delimiters and is never treated as instructions.
* Credentials are held by the Tool Manager and never enter an agent's context, so
  injected text cannot cause a token to be echoed.
* Because every state change is gated on a human click showing the real payload, a
  successful injection still cannot silently change the user's data. This is the
  property that makes the whole design safe rather than merely careful.

## Alternatives considered

* **Trust the agent and log afterwards.** Smoother, and typical of AI demos. Rejected:
  it directly contradicts `docs/12`, and "Ray deleted my calendar and logged it" is not
  an acceptable outcome.
* **Approve per integration connection, not per call.** One-time consent, but it gives
  blanket authority and shows the user nothing about the specific action taken.
* **Confirm in natural language ("shall I?") instead of a UI card.** Feels
  conversational, but the confirmation is produced by the same model that may have been
  injected, and it is not auditable. The gate must live outside the model.

## Consequences

* An `approvals`/`tool_invocations` table and an `ApprovalCard` component are V1 scope,
  and `docs/06`, `docs/08`, and `docs/09` are updated accordingly.
* The orchestrator's tool loop must be able to suspend and resume across a user
  decision, which the SSE stream (ADR-0007) already supports.
* Slight friction in normal use, mitigated by standing approvals for low-risk internal
  tools.
