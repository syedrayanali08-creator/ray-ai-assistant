# ADR-0002 — PostgreSQL + pgvector as the single data store

## Status

Accepted.

## Context

`docs/02`, `docs/05`, and `docs/06` name PostgreSQL as the preferred database and
"PostgreSQL with vector extensions" or a local vector database for semantic memory.
The decision was left open. Ray needs both relational data (tasks, projects, events,
messages) and semantic search over memories, and memory retrieval routinely needs both
at once: "find memories similar to this question, but only for the active project, and
weight recent ones higher".

## Decision

**PostgreSQL 16 with the `pgvector` extension, as the single store for everything.**
Run locally via `docker-compose` using the `pgvector/pgvector:pg16` image, so setup is
one command as `docs/13` requires.

Memory embeddings live in a `vector(384)` column on the `memories` table, indexed with
HNSW. Retrieval is therefore a single SQL query that can filter on category, project,
importance, and recency *and* order by vector distance — no application-side joining
between two systems.

## Alternatives considered

* **SQLite + sqlite-vec.** Zero infrastructure, genuinely simpler for one user, and
  tempting. Rejected because Ray's schema will churn through eight phases and Postgres
  handles concurrent access, JSON columns, real constraints, and later multi-user
  cleanly. The docs also explicitly prefer Postgres, and "could theoretically become
  multi-user" is a stated goal.
* **Postgres for relational data + Chroma/Qdrant for vectors.** Better vector features,
  but introduces a second store to run, back up, and keep in sync. A hybrid query then
  requires fetching candidates from one system and filtering in Python, which is both
  slower and more code. Not justified at personal-assistant data volumes (thousands of
  memories, not millions).
* **A hosted vector service.** Violates the no-paid-services and privacy requirements.

## Consequences

* Docker is a hard prerequisite for development. Acceptable, and it keeps setup to one
  command.
* Vector index tuning is on us, but at this data volume HNSW defaults are fine.
* Schema changes need migrations from day one — see ADR-0012 (Alembic).
* Backups are a single `pg_dump`, which also satisfies the "user owns their data"
  export requirement in `docs/12`.
