# Ray — Personal AI Assistant

Ray is a personal, Jarvis-inspired AI assistant: a single conversational surface backed
by persistent memory, specialized agents, and tools that reach into the systems its user
already lives in — calendar, GitHub, notes, and local files.

Ray is built for one person, runs locally, and costs nothing to operate.

> **Status: pre-implementation.** The specification in [`/docs`](docs/) is complete and
> all technical decisions are recorded in [`/docs/adr`](docs/adr/). Phase 1 is next; see
> the [roadmap](docs/10%20Development%20Roadmap.md).

---

## What Ray does

| Capability | Description |
|---|---|
| **Conversation** | Text and voice, including wake-word activation ("Ray") |
| **Memory** | Remembers projects, goals, preferences, and learning progress, and uses them automatically |
| **Planning** | Tasks, deadlines, priorities, scheduling, and time blocking |
| **Coding mentorship** | Understands active projects and teaches rather than replacing the user's work |
| **Learning** | Explains, quizzes, tracks proficiency, and adapts depth accordingly |
| **Research** | Turns open-ended curiosity into structured, actionable plans |
| **Transparency** | Always reports which agent, tools, and memories produced an answer |

---

## Architecture at a glance

```
        Voice / Text
             │
   Next.js dashboard (HUD)
             │  REST + SSE
       FastAPI backend
             │
          Ray Core            context assembly, orchestration, trace
             │
      Executive Agent         routes to one specialist by default
             │
  ┌──────────┼──────────┬──────────┐
Planning  Coding    Learning   Research      (code modules, not DB rows)
             │
       Tool Manager           permissions, approval gate, error handling
             │
  Adapters → Integrations     GitHub, calendar, Obsidian, local files
             │
  Memory service  ←→  PostgreSQL + pgvector
```

Three rules hold the design together, and are enforced structurally by import rules in
CI:

1. Agents never touch the database — only services do.
2. Agents never touch external services — only the Tool Manager does.
3. Nothing that changes state runs without explicit user approval.

---

## Technology

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic | Best AI ecosystem; async suits streaming and tool calls ([ADR-0012](docs/adr/0012-backend-stack.md)) |
| Database | PostgreSQL 16 + pgvector | One store for relational data *and* semantic memory ([ADR-0002](docs/adr/0002-postgres-pgvector.md)) |
| LLM | Provider abstraction: Gemini (default), Groq, Ollama | Never locked to one provider; degrades instead of breaking ([ADR-0001](docs/adr/0001-llm-provider-abstraction.md)) |
| Embeddings | Local `sentence-transformers` (`all-MiniLM-L6-v2`) | Free, fast, and the memory corpus never leaves the machine ([ADR-0003](docs/adr/0003-local-embeddings.md)) |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind v4, shadcn/ui | Bespoke HUD without fighting a theme ([ADR-0011](docs/adr/0011-frontend-stack.md)) |
| Streaming | Server-Sent Events | One-directional flow; plain HTTP, reuses existing auth ([ADR-0007](docs/adr/0007-sse-streaming.md)) |
| Voice | openWakeWord, faster-whisper, Piper — all local | Voice-first from Phase 1, free, private ([ADR-0009](docs/adr/0009-voice-first-architecture.md)) |

Everything is free and open-source. The only external dependency is an LLM free tier,
and setting `RAY_LLM_PROVIDER=ollama` removes even that.

---

## Quickstart

> Available from Phase 1. Documented here so the target setup experience is fixed up
> front: a new developer must be able to run Ray from this file alone (`docs/13`).

```bash
git clone https://github.com/syedrayanali08-creator/ray-ai-assistant.git
cd ray-ai-assistant

cp .env.example .env          # then set RAY_API_TOKEN and your LLM key

docker compose up -d          # PostgreSQL + pgvector

cd backend && uv sync && uv run alembic upgrade head && uv run python scripts/seed.py
uv run uvicorn ray.main:app --reload      # http://127.0.0.1:8000

cd ../frontend && pnpm install && pnpm dev # http://localhost:3000
```

---

## Privacy

* Memory, embeddings, and pre-activation microphone audio **never leave the machine**.
* Conversation text **is** sent to the configured LLM provider. The default is Google's
  Gemini free tier; `RAY_LLM_PROVIDER=ollama` keeps everything local.
* The API always requires a bearer token and binds to `127.0.0.1` by default.
* No secret is ever stored in the database — only a reference to where it lives.

Details in [`docs/12 Security and Privacy`](docs/12%20Security%20and%20Privacy.md).

---

## Documentation

`/docs` is the source of truth for *what* Ray is. `/docs/adr` is the source of truth for
*how* it is built and *why*.

| | |
|---|---|
| [00 Vision](docs/00%20Vision.md) | What Ray is for |
| [01 Product Requirements](docs/01%20Product%20Requirements.md) | Functional requirements and MVP criteria |
| [02 Technical Architecture](docs/02%20Technical%20Architecture.md) | System structure |
| [03 Agent Specifications](docs/03%20Agent%20Specifications.md) | Each agent's purpose, tools, and limits |
| [04 Integrations and Tool System](docs/04%20Integrations%20and%20Tool%20System.md) | Tool Manager, adapters, priority |
| [05 Memory System](docs/05%20Memory%20System.md) | Memory model and behaviour |
| [06 Database and Data Model](docs/06%20Database%20and%20Data%20Model.md) | Schema |
| [07 Learning and Teaching System](docs/07%20Learning%20and%20Teaching%20System.md) | How Ray teaches |
| [08 API Specification](docs/08%20API%20and%20Backend%20Interface%20Specification.md) | Endpoints and streaming contract |
| [09 UI and UX Specification](docs/09%20UI%20and%20UX%20Specification.md) | Dashboard and components |
| [10 Development Roadmap](docs/10%20Development%20Roadmap.md) | **Canonical phase order** |
| [12 Security and Privacy](docs/12%20Security%20and%20Privacy.md) | Data handling and approval model |
| [13 Testing and Deployment](docs/13%20Testing%20and%20Deployment.md) | Testing strategy and release process |
| [15 Evaluation](docs/15%20Evaluation.md) | How AI behaviour is measured |
| [ADRs](docs/adr/) | Every resolved technical decision |
