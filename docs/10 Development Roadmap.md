# Ray — Development Roadmap

## Purpose

This document defines the implementation order for Ray.

**This document is the canonical development order.** Where `docs/01` and `docs/14`
previously listed their own priority orders, they now defer to this file.

The goal is a working personal AI assistant as quickly as possible, on a structure that
allows future expansion. Each phase produces a usable improvement, and no phase breaks a
previous one.

---

# Development Strategy

* Build incrementally. One working component at a time.
* Every phase ends with: it runs, it is tested, its docs are updated, and it can be
  demonstrated.
* Do not build advanced features before the foundation exists.
* **Voice is architected from Phase 1 and implemented progressively** (ADR-0009). No
  phase blocks on voice quality, and no phase leaves voice impossible to add.

Technical decisions referenced below are recorded in `docs/adr/`.

---

# Phase 0 — Decisions and Scaffolding

## Goal

Resolve every open technical decision and stand up the development environment before
any feature code is written.

## Tasks

* Architecture Decision Records for all major choices (ADR-0001 … ADR-0014)
* Update `/docs` to match the decisions (schema, API, UI, integrations, security)
* `docker-compose.yml` with PostgreSQL + pgvector
* Backend and frontend project skeletons
* `.env.example` documenting every variable
* Linting, type checking, tests, and CI wired up
* Pre-commit hooks
* `README.md` with a working quickstart

## Completion Criteria

* every contradiction in the documentation is resolved and recorded
* `docker compose up` plus one dev command boots an empty frontend and backend
* CI is green on an empty project

---

# Phase 1 — Foundation

## Goal

Create the basic Ray application structure with the real data model in place.

## Tasks

* Full V1 database schema (`docs/06`) with the first Alembic migration
* Seed script creating the single local user
* FastAPI application with health, config, and the single-user auth dependency
  (ADR-0006)
* Typed frontend API client generated from OpenAPI
* Jarvis-style dashboard shell: status bar, conversation area, panel rail
* **Voice architecture stubs:** `ray/voice/` interfaces, modality-aware core contract,
  `speech_text` on the message model (ADR-0009)

## Completion Criteria

Ray can:

* run locally from a clean clone by following the README
* display the dashboard
* communicate between frontend and backend against real seeded data

---

# Phase 2 — Core AI Conversation

## Goal

Create the main Ray interaction system.

## Tasks

* `LLMProvider` abstraction with the Gemini and Ollama adapters, plus a `mock` provider
  that terminates the fallback chain (ADR-0001, ADR-0015). Groq is deferred to the phase
  that introduces routing, since nothing routes yet.
* Executive Agent in single-agent mode (no routing yet)
* `POST /chat/message` streaming over SSE (ADR-0007)
* Conversation and message persistence, conversation history
* Retrieval and embedding *interfaces* only — `NullRetriever` returns nothing and the
  `memory` trace event is emitted with `count: 0`, so Phase 3 is a swap rather than a
  change to the pipeline
* Chat UI with markdown, code formatting, and streaming rendering
* **Voice round trip using browser STT/TTS fallbacks** — low quality, but Ray can be
  spoken to and can speak back

## Completion Criteria

User can:

* open Ray, type or speak a message, and receive a streamed response
* continue and revisit conversations
* switch LLM provider with one environment variable
* run Ray with **nothing** configured and still get an answer that explains what to
  configure

---

# Phase 3 — Memory System

## Goal

Give Ray persistent knowledge that measurably changes its answers.

## Tasks

* Local embeddings (ADR-0003) and the `memories` table with an HNSW index, with a
  dependency-free hashing backend so CI exercises real similarity without torch
  (ADR-0016)
* Write path: extraction, importance scoring, dedupe and merge (ADR-0013), running
  **after** the response is streamed so learning never adds latency
* Retrieval: hybrid similarity + importance + recency + usage scoring, ranked in SQL
* Context assembly with a token budget, dropping whole memories rather than truncating
* Memory API and Memory view: search, edit, delete, disable categories, view provenance
* `docs/15` evaluation set covering memory behaviour, run through the real pipeline

## Completion Criteria

* in a brand-new conversation Ray correctly answers "what am I working on?"
* deleting a memory immediately stops Ray using it
* the evaluation set passes

---

# Phase 4 — Agent System and Tool Manager

## Goal

Create specialized Ray capabilities behind one conversational surface.

## Tasks

* Agent base class and registry (ADR-0005)
* Planning, Coding, Learning, and Research agents; memory exposed as a service and a
  tool rather than an agent
* Executive routing via function calling, single-agent by default, explicit fan-out for
  cross-domain requests (ADR-0008)
* Tool Manager: registry, permissions, timeouts, error normalisation, activity logging
* Approval gate and approval cards for side-effecting tools (ADR-0014)
* Internal tools: tasks, projects, calendar, memory
* Agent Status panel and agent trace visualization

## Completion Criteria

* Ray routes requests to the appropriate agent and says which one it used
* the "Plan my week" user flow from `docs/13` works end to end
* no side-effecting tool can run without explicit approval
* the agent, tool, and approval test suites pass (ADR-0017)

## Status

Complete. The routing, specialist agents, Tool Manager, approval gate, and trace/approval UI are wired into the conversation and memory pipeline.

---

# Phase 5 — Productivity Surfaces and Integrations

## Goal

Connect Ray with the user's existing tools, in priority order (ADR-0010).

## Tasks

* Task, Project, and Calendar views; project dashboards with progress
* **GitHub (priority 1):** read-only repository tree, file contents, commits, issues
* **Calendar (priority 2):** local calendar as default, ICS import/export, optional
  Google Calendar sync behind the same adapter
* **Knowledge (priority 3):** Obsidian vault read/create/link; Notion optional
* **Local files (priority 4):** read and summarise within allow-listed directories
* Integration API and a settings page with per-integration permission controls

## Completion Criteria

* Ray answers "what should I work on next in Starfall Sprint?" using the real repository
* Ray can view and create calendar events, with creation gated by approval
* integrations fail loudly and explain themselves

---

# Phase 6 — Voice Interaction

## Goal

Deliver the voice-first experience properly.

## Status

**Hardened and merge-ready.** Local STT/TTS/wake are genuinely usable and can be set up
with one download script. The browser fallback remains available by default.

## Tasks

* [x] Local speech-to-text with `faster-whisper`
* [x] Local text-to-speech with Piper
* [x] `/voice/stream` WebSocket for post-activation audio
* [x] Listening / Processing / Responding states in the UI
* [x] Latency tuning on the spoken path
* [x] `scripts/download_voice_models.py` to fetch Piper and pre-load Whisper
* [x] `voice_models_dir` setting so relative `tts_voice` paths resolve correctly
* [x] Wake-word keyword fallback using faster-whisper when `openwakeword` is unavailable

## Sub-phase 6b — Wake Word

* [x] Wake-word detection running in the client (browser `SpeechRecognition` for V1;
  server-side `openWakeWord` is wired behind the same interface)
* [x] Support both "Ray" and "Jarvis" as wake-word aliases (`WakeEvent` records which
  phrase fired); the spoken persona stays "Ray"
* [x] Always-listening indicator and a revocable microphone permission
* [x] Barge-in (interrupting Ray while it speaks)
* [x] Usable server-side keyword fallback without a dedicated wake-word model

## Completion Criteria

* [x] `uv run python scripts/download_voice_models.py` downloads the required voice model(s)
  and the local STT/TTS pipeline runs
* [x] the user says "Ray" or "Jarvis", speaks a request, and hears a natural spoken answer
* [x] the wake word runs locally and no audio leaves the machine before activation

---

# Phase 7 — Advanced Dashboard

## Goal

Complete the Jarvis-style experience.

## Tasks

* HUD design pass: dark theme, glow, system panels
* Cinematic reactor-inspired ambient visuals driven by voice/trace state (idle, listening,
  thinking, speaking, awaiting approval) with `prefers-reduced-motion` support
* Agent flow visualization and richer Ray Status
* Project, memory, and learning panels
* Purposeful motion only; empty, loading, and error states everywhere
* Keyboard-first navigation

## Completion Criteria

`docs/09` completion criteria are met and the interface is portfolio quality.

---

# Phase 8 — Self Improvement and Hardening

## Goal

Make Ray easy to keep improving, and safe to rely on.

## Tasks

* Structured logging, error taxonomy, and secret redaction
* Integration health checks with self-diagnosis messaging
* "Ray, this workflow is annoying" → improvement task flow (`docs/04`)
* Configuration management UI
* Full data export and backup
* Release tagging and changelog per `docs/13`

---

# Development Priorities

1. Working application
2. AI conversation
3. Memory
4. Agents
5. Integrations
6. Voice quality and wake word
7. Visual polish
8. Advanced automation

Voice *architecture* is not in this priority list because it is a Phase 1 constraint,
not a later feature.

---

# Testing Requirements

Every major feature ships with:

* functionality tests
* error-handling tests
* updated documentation
* additions to the evaluation set in `docs/15` where AI behaviour is involved

Do not add features that break existing functionality.

---

# Free Technology Requirement

Prefer free APIs, open-source tools, local solutions, and free hosting tiers. Avoid paid
dependencies, subscriptions, and vendor lock-in. Any unavoidable paid dependency must be
identified, justified, and approved before adoption.

---

# Definition of Complete Version 1

Ray V1 is complete when:

* the user can interact through text and voice
* Ray remembers user context and uses it
* Ray manages tasks, schedules, and projects
* Ray assists with coding, teaching, and research
* Ray connects to external tools through the Tool Manager
* Ray explains which agent, tool, and memories it used
* Ray has a polished Jarvis-inspired dashboard
* Ray runs locally with no paid services

---

# Phase 9 — Specialized Agents

## Goal

Add new domains once routing and the existing agent/tool model are solid.

## Candidate domains

* **Fitness** — workout programmes, progression tracking, recovery and sleep patterns.
* **Content creation** — drafting, editing, repurposing one piece across formats,
  maintaining a consistent voice.
* **Personal finance** — budgets, subscriptions, savings goals. Local-only provider
  and stricter memory policy by default (ADR-0013, ADR-0015).
* **Health and habits, travel planning, home/inventory** — plausible, unscoped.

## Entry criteria

1. Routing is reliable; a new domain must not be reached by accident.
2. The domain needs its own tools or memory shape, not just a different system prompt.

---

# Phase 10 — Desktop Packaging

## Goal

Hide the terminal/Docker/backend/frontend setup behind a one-click installable app.

## Tasks

* macOS first: bundled PostgreSQL (or embedded equivalent), auto-launch backend and
  frontend, menu-bar presence.
* Auto-update and signed releases.
* Extend to Windows and Linux once the packaging and local-first data stories are solid.

## Constraint

The packaged app is a distribution layer, not a runtime change. The backend, frontend,
and agent system must keep working as a normal web deployment.

---

# Backlog Process

Directions that are not yet in a phase live as short notes in this repo's issue tracker
or as `## Future` subsections inside ADRs. A direction is only promoted into a phase when
it has clear entry criteria and does not destabilize the current phase.
