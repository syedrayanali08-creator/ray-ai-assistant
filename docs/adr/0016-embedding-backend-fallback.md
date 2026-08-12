# ADR-0016 — Embeddings degrade to a hashing backend instead of failing

## Status

Accepted. Extends ADR-0003 (local embeddings) and applies the ADR-0015 degradation
principle to the memory system.

## Context

ADR-0003 chose local `sentence-transformers/all-MiniLM-L6-v2` embeddings: free,
private, 384 dimensions, good enough for personal-scale retrieval. Implementing Phase 3
exposed a cost that decision did not weigh.

`sentence-transformers` pulls in **torch** — a multi-hundred-megabyte install and a
several-second import. That is acceptable on the machine Ray runs on. It is not
acceptable in two other places:

* **CI.** Every pull request would install and warm a neural model to run tests whose
  subject is *ranking policy*, not embedding quality. Retrieval tests would also become
  slow enough that developers stop running them locally.
* **A fresh clone.** Under ADR-0003 as written, a machine without the optional install
  gets a hard failure the first time anything is remembered — the same first-minute
  failure ADR-0015 rejected for LLM providers.

The obvious alternative — mocking the embedder in tests — was rejected. A mock that
returns fixed vectors cannot exercise the dedupe thresholds, which are the part of
ADR-0013 most likely to break, because those thresholds are statements about *real*
similarity values.

## Decision

**There are two embedding backends behind `TextEmbedder`, selected by
`RAY_EMBEDDING_BACKEND`:**

| Backend | What it is | Where it is used |
|---|---|---|
| `sentence-transformers` (default) | ADR-0003's model | Ray as the user runs it |
| `hashing` | Hashed word and character trigrams, L2-normalised, 384 dimensions | CI, tests, and any machine without the optional install |

**The hashing backend is a real embedder, not a stub.** Texts sharing words land near
each other, cosine similarity is meaningful and stable, and the vectors are the same
width as the model's, so the same column, the same HNSW index, and the same SQL are
exercised. Measured on the dedupe fixtures: a restatement of the same fact scores
~0.93, an unrelated fact ~0.04 — comfortably either side of the 0.85/0.95 thresholds.

What it does **not** have is semantics. It cannot tell that "university plans" and
"applying to Waterloo" are related. That is precisely the capability the model backend
provides, and it is why the model backend remains the default.

**Requesting the model backend without the install degrades rather than fails.** A
missing torch logs `memory.embedder_unavailable` with the command to fix it and falls
back to hashing, consistent with ADR-0015: a setup gap is a state Ray reports, not a
crash.

## Consequences

* CI is fast and needs no model download, while still testing dedupe, merge, ranking,
  and the pgvector query end to end.
* Switching backends **changes the vector space**, so existing embeddings become
  meaningless — a switch requires re-embedding. Recorded in `docs/05`; the memory stats
  endpoint reports rows with no vector so the condition is visible.
* Evaluation cases must be phrased in overlapping vocabulary to run under the hashing
  backend. That is a real limit: cases that genuinely test *semantic* recall must be
  run against the model backend, and `docs/15` says so.
* A future upgrade (a larger local model, a different dimension) is now a backend
  addition plus a migration, not a change to any calling code.
