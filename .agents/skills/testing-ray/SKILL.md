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
- Editing `frontend/.env.local` while `pnpm dev` is running makes the dev server print
  `Reload env: .env.local` and then **exit** (`ELIFECYCLE Command failed`). After any
  `.env.local` edit, expect to relaunch `pnpm dev` and re-check `curl -o /dev/null -w
  '%{http_code}' localhost:3000` before driving the browser.
- Launch each server in its **own** `exec` call. Chaining `setsid nohup ... & sleep 25;
  curl ...` in one call often has the server die with the parent shell when the call is
  backgrounded; launch first, then poll health in a separate call.

## Provider modes (Phase 2)

`RAY_LLM_PROVIDER` selects the head of the chain; `mock` always terminates it.

```bash
# fallback demo: ollama isn't installed, so the chain degrades to mock
RAY_LLM_PROVIDER=ollama setsid nohup uv run uvicorn ray.main:app --port 8000 ...
# deterministic answers, no network
RAY_LLM_PROVIDER=mock   setsid nohup uv run uvicorn ray.main:app --port 8000 ...
```

- Confirm the active chain with `curl -H "Authorization: Bearer $RAY_API_TOKEN"
  localhost:8000/chat/providers` — the first entry is the preferred provider, and the
  status bar / composer hint in the UI echoes it (GEMINI / OLLAMA / MOCK).
- A degraded answer shows a `FALLBACK` marker on the trace line plus a
  `compose: "<provider> unavailable — used the fallback"` step. Pure `mock` mode shows
  the canned reply with **no** fallback marker — that difference is the assertion.

## Chat UI selectors

- Composer: `textarea[aria-label="Message Ray"]`; Enter sends, Shift+Enter newlines,
  whitespace-only keeps Send `disabled`.
- Trace line: the `button[aria-expanded]` inside each assistant `<article>`.
- Voice: `aria-label="Arm wake word listening"`, `"Push to talk"`,
  `"Toggle spoken replies"`. Headless/standard Chrome here has **no** Web Speech API, so
  the first two render `disabled` with title "This browser has no speech recognition".
  Real speech in/out cannot be exercised without a microphone — mark it untested and
  lean on `pnpm test` (vitest covers wake-word matching, SSE reassembly, and turn bookkeeping).
- Typing a >9 000-char message via the computer tool is very slow; use
  `DISPLAY=:0 xdotool type --delay 1 "$TXT"` after clicking the textarea (takes a few
  minutes — run it backgrounded and poll).

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
  grep over every `/_next/static/chunks/*.js` referenced by the HTML. For Phase 2 also
  grep the proxied SSE body:
  `curl -s -N -X POST localhost:3000/api/chat -H 'content-type: application/json' -d
  '{"message":"leak check"}'` — the browser never sends the token; the Next.js route
  handler at `src/app/api/chat/route.ts` attaches it server-side.
- Never print/screenshot `RAY_GEMINI_API_KEY`. Assert secrecy by comparing counts:
  `grep -c -F "$KEY"` over the HTML, JS chunks, SSE body and `/chat/providers` (all 0).
- `/chat/message` only ever returns non-200 for **401 or 422**. Provider failures after
  the first token arrive as an in-band SSE `error` event, so a 200 does not mean the
  answer succeeded — parse the event stream.
- An unknown `conversation_id` POSTed to `/chat/message` is deliberately treated as a
  **new** conversation (`conversation_service.get_or_create`) rather than 404, so the
  user's message is never lost. Unknown ids on `GET`/`DELETE /chat/{id}` do 404.
- Cross-user isolation: insert a second user with
  `INSERT INTO users (id,name,preferences,settings,created_at,updated_at) VALUES
  (gen_random_uuid(),'Intruder','{}'::jsonb,'{}'::jsonb,now(),now())` — `preferences`
  **and** `settings` are both NOT NULL. Their conversation must 404 on GET/DELETE and
  must still exist in the DB afterwards (prove the 404 wasn't a silent delete).

## Devin Secrets Needed

None — all values are local dev defaults in `.env.example`.
