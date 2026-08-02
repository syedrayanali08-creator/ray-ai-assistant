# ADR-0012 — FastAPI + SQLAlchemy + Alembic backend and tooling

## Status

Accepted.

## Context

`docs/02` mandates Python and FastAPI. The remaining choices — ORM, migrations, package
manager, testing, and the internal layering that keeps `docs/04` and `docs/08`'s
separation rules enforceable — were undecided.

## Decision

* **Python 3.12 + FastAPI + Uvicorn.** Mandated; async suits streaming and concurrent
  tool calls, and automatic OpenAPI generation feeds the frontend's generated types.
* **SQLAlchemy 2.0 (async) + asyncpg.** Typed, modern, and the mature option for
  Postgres in Python. `pgvector`'s SQLAlchemy integration gives a first-class `Vector`
  column type.
* **Alembic** for migrations, from the very first table. Ray's schema changes in every
  phase; hand-edited SQL would desynchronise from the models immediately.
* **Pydantic v2 + pydantic-settings.** Request/response schemas and env-driven config,
  both FastAPI-native. All configuration is env vars with typed validation — no secrets
  in code, per `docs/12`.
* **`uv`** for dependency management and virtualenvs: dramatically faster than pip and
  produces a lockfile, so environments are reproducible.
* **`ruff`** (lint + format) and **`mypy`** (strict on `ray/`), both in pre-commit and CI.
* **`pytest` + `pytest-asyncio` + `httpx.AsyncClient`** for tests; **testcontainers** or
  a disposable compose service for a real Postgres in integration tests, because
  pgvector behaviour cannot be tested against SQLite.
* **`structlog`** for structured JSON logs with a secret-redaction processor, so an
  error can never print an API key (`docs/12`).

### Enforced layering

```
api/      HTTP only — validation, auth dependency, serialisation. Never imports db/.
core/     orchestration. Calls agents, memory, services.
agents/   reasoning. May import llm/ and tools/. Never imports db/ or integrations/.
tools/    Tool Manager + tool implementations. The only caller of integrations/.
services/ business logic. THE ONLY layer that touches db/.
db/       models, session, engine.
```

This is `docs/04`'s "agents never touch external services" and `docs/08`'s "agents never
touch the database" turned into a structural property. An import-linter rule in CI fails
the build on violation, so the architecture cannot erode quietly.

## Alternatives considered

* **Django + DRF.** Batteries included and an admin panel for free, but heavier, less
  natural async, and its conventions fight the agent/tool layering.
* **SQLModel.** Nice ergonomics over SQLAlchemy, but a thinner abstraction with less
  control over async sessions and complex vector queries.
* **Raw SQL, no ORM.** Full control and no magic, but eight phases of schema churn
  without migrations or model types is a poor trade.
* **Poetry / pip-tools instead of uv.** Both fine; uv is faster and increasingly the
  default.

## Consequences

* Async everywhere means blocking calls (sentence-transformers, faster-whisper) must be
  pushed to a thread pool or they will stall the event loop.
* Integration tests need Docker.
* The import-linter rules must be maintained as new packages appear.
