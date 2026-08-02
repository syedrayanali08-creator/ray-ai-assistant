# ADR-0013 — Memory write, dedupe, and retrieval policy

## Status

Accepted. Fills the gaps in `docs/05`.

## Context

`docs/05` states the principle "useful over complete" and requires automatic context
retrieval, but never defines what triggers a write, how duplicates are avoided, how
importance is decided, or how retrieval ranks results. Without these rules, Ray either
stores everything (and retrieval becomes noise) or stores nothing useful.

## Decision

### What gets written

Memory extraction runs **after** a response is produced, off the critical path, so it
never adds latency to a reply. A cheap LLM call (the router provider, ADR-0001) is asked
to extract zero or more candidate memories from the exchange, each with a category,
content, and importance.

A candidate is stored only if it is **durable** — true beyond this conversation — and
**actionable** — it would change a future response. Explicitly not stored: the content of
the current request, one-off factual questions, anything already derivable from the
`projects`/`tasks`/`learning_records` tables (structured data is not duplicated into
prose memories), and anything the user marks private.

The user can always force a write with "Ray, remember that…", which bypasses the
importance threshold.

### Categories

`user` (preferences, communication style), `project`, `learning`, `goal`, `conversation`.
Each category can be disabled by the user, per `docs/05` and `docs/12`.

### Importance

A 1–5 integer set at extraction time. 1–2 is stored but rarely retrieved; 4–5 is
effectively always in context when topically relevant. Importance decays for
`conversation` memories that are never retrieved (see expiry).

### Dedupe

Before insert: embed the candidate and search existing memories in the same category.

* cosine similarity **≥ 0.95** → discard as duplicate, bump the existing memory's
  `updated_at` and `hit_count`.
* **0.85–0.95** → treat as an **update**: the LLM merges old and new into one memory and
  supersedes the old row (`superseded_by` is set rather than deleting, so history is
  auditable).
* **< 0.85** → insert as new.

This is what prevents the classic failure of accumulating fifty near-identical "user is
building a Processing game" rows.

### Provenance

Every memory records `source` (conversation / user / tool), `source_message_id`, and
`why` — a one-line justification. This is what the memory dashboard's "see why a memory
exists" requirement in `docs/05` needs, and it is what makes an incorrect memory
debuggable rather than mysterious.

### Retrieval scoring

Retrieval is hybrid, not pure vector search:

```
score = 0.55 * cosine_similarity
      + 0.20 * importance_normalised
      + 0.15 * recency_decay(updated_at, half_life=30d)
      + 0.10 * usage(hit_count)

+ hard filters: user_id, enabled categories, not superseded
+ boost: memories attached to the active project when one is in context
```

Weights are configuration, tuned against the eval set in `docs/15`. Pure similarity is
insufficient because it ignores that a stale, unimportant memory can be textually
similar to an urgent one.

The top *k* memories are added to context under a token budget (default: 25% of the
context window for memories), truncating by score.

### Lifetime and expiry

* **Short-term** — the last N messages of the current conversation, always included.
* **Working memory** — memories tagged with an active session/project context; retrieved
  preferentially for 7 days, then treated as normal long-term memories.
* **Long-term** — no automatic deletion. `conversation`-category memories with
  importance ≤ 2 and zero retrievals in 90 days are flagged for review in the memory
  dashboard, never silently deleted. Ray does not delete the user's data on its own.

### User control

View, search, edit, delete, and disable-by-category, per `docs/05`. A deleted memory is
hard-deleted, and deletion is immediately reflected in retrieval — the eval set includes
a test asserting exactly this.

## Alternatives considered

* **Store every message as a memory.** Simple, and semantic search "handles it" — but
  retrieval quality collapses as noise dominates, which is precisely what `docs/05`'s
  "useful over complete" warns against.
* **Pure vector similarity retrieval.** Simplest scoring, but ignores importance and
  recency and produces confidently stale answers.
* **A knowledge graph.** Better relational reasoning and listed as a future improvement
  in `docs/05`. Far more work; revisit once the flat store proves limiting.
* **Synchronous extraction during the response.** Fresher memory, but adds an LLM call
  to every user-visible latency path.

## Consequences

* Extraction costs one extra cheap LLM call per exchange (async, off the hot path).
* Weights need tuning; without the `docs/15` eval set this becomes guesswork, which is
  why that document is a prerequisite for Phase 3.
* Superseded rows accumulate — cheap to store, and valuable for auditing.
