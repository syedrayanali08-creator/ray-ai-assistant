---
name: testing-ray
description: How to bring up and test the Ray personal AI assistant stack (Postgres+pgvector, FastAPI backend, Next.js HUD dashboard) locally.
---

# Testing Ray locally

## Bring up the stack

```bash
cd <repo>
docker compose up -d                       # Postgres 16 + pgvector on :5433 (container "ray-db")
cd backend && uv sync && uv run alembic upgrade head && uv run python scripts/seed.py
setsid nohup uv run uvicorn ray.main:app --port 8000 > /tmp/ray-api.log 2>&1 < /dev/null &
cd ../frontend && pnpm install && cp ../.env .env.local
setsid nohup pnpm start > /tmp/ray-fe.log 2>&1 < /dev/null &   # or pnpm dev
```

- Use `setsid nohup ... < /dev/null &`. A plain `nohup ... &` inside a one-shot shell
  tool call gets killed when the call times out, silently taking the server down.
- `.env` / `frontend/.env.local` are git-ignored; the local dev token is
  `RAY_API_TOKEN=local-dev-token`.
- The frontend reads `RAY_API_TOKEN` **server-side only**. Changing it requires
  restarting the Next.js process — a browser reload alone is not enough.

## Restart the backend before you trust a failure

A long-lived uvicorn process can serve stale source (tracebacks whose line numbers point
at comments are the tell). If an API route 500s unexpectedly, kill and restart uvicorn
and re-run before reporting it as a bug.

## Resetting seed data

`scripts/seed.py` is idempotent and will NOT recreate rows you deleted. For a clean
slate:

```bash
docker exec ray-db psql -U ray -d ray -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
cd backend && uv run alembic upgrade head && uv run python scripts/seed.py
```

## Useful facts for writing assertions

- Enum values are stored UPPERCASE in Postgres (`taskstatus` = TODO/IN_PROGRESS/
  BLOCKED/DONE/CANCELLED) but are lowercase in JSON. `UPDATE tasks SET status='done'`
  fails; use `'DONE'`.
- Every route except `/health` requires `Authorization: Bearer $RAY_API_TOKEN` → 401.
- `/dashboard` returns 503 (not 500) when the `users` table is empty. To simulate:
  rename `users`, create an empty clone, then rename back.
- `tasks.project_id` is `ON DELETE SET NULL`, so deleting a project must leave its tasks
  alive with `project_id: null` and no PROJECT badge in the UI.
- Token-leak check: `curl -s localhost:3000/ | grep -c local-dev-token` plus the same
  grep over every `/_next/static/chunks/*.js` referenced by the HTML.

## Devin Secrets Needed

None — all values are local dev defaults in `.env.example`.
