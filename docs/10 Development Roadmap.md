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

## Tasks

* Local speech-to-text with `faster-whisper`
* Local text-to-speech with Piper
* `/voice/stream` WebSocket for post-activation audio
* Listening / Processing / Responding states in the UI
* Latency tuning on the spoken path

## Sub-phase 6b — Wake Word

* openWakeWord "Ray" detection running in the client
* Always-listening indicator and a revocable microphone permission
* Barge-in (interrupting Ray while it speaks)

## Completion Criteria

* the user says "Ray", speaks a request, and hears a natural spoken answer
* the wake word runs locally and no audio leaves the machine before activation

---

# Phase 7 — Advanced Dashboard

## Goal

Complete the Jarvis-style experience.

## Tasks

* HUD design pass: dark theme, glow, system panels
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

# Beyond the Roadmap — Directions, Not Commitments

Recorded so they shape the architecture now and are not lost. None of these are
scheduled, and nothing below should be implemented until it is promoted into a phase
above.

## Two wake words: "Ray" and "Jarvis"

Both names should activate Ray. This is a deliberate design note rather than a
nice-to-have, because it constrains the wake-word interface: `WakeEvent` must carry
*which* phrase fired, and the detector must accept a **list** of keywords rather than
one. openWakeWord supports multiple simultaneous models, so the cost is a second model
file, not a second pipeline. The spoken persona stays "Ray"; "Jarvis" is an alias, not
a second assistant.

## Cinematic reactor-inspired HUD

The interface should evolve toward the Iron Man arc-reactor aesthetic: a circular,
concentric-ring centrepiece that visibly *reacts* — idle breathing, a listening pulse on
wake, an inward gather while thinking, an outward bloom while speaking. Ambient depth
(scan lines, subtle glow, angular chrome) around a calm core.

The constraint is that it must stay clean and usable. Two rules follow, and they are the
whole point of writing this down early:

* **Motion is state, not decoration.** Every animation maps to a real system state that
  already exists in the trace stream (idle, listening, thinking, tool call awaiting
  approval, speaking). If a viewer cannot name what an animation means, it should not
  ship.
* **Text stays flat and readable.** The cinema lives in the ambient layer and the
  reactor; conversation, code blocks, and task lists remain high-contrast and
  unornamented. A HUD that is hard to read is a worse HUD.

`prefers-reduced-motion` must be honoured, and the reactor must degrade to a static
state indicator without losing information.

## Further specialized agents

The agent registry is code (ADR-0005), so a new domain is a new module plus a prompt.
Candidate domains, in no order:

* **Fitness** — workout programmes, progression tracking, recovery and sleep patterns.
* **Content creation** — drafting, editing, repurposing one piece across formats,
  maintaining a consistent voice.
* **Personal finance** — budgets, subscriptions, savings goals. This one needs care:
  financial data is the most sensitive category Ray would hold, and it likely argues for
  a local-only provider (ADR-0015) and a stricter memory policy (ADR-0013).
* **Health and habits, travel planning, home/inventory** — plausible, unscoped.

Two things must be true before any of them is worth building:

1. **Routing exists and is good.** More agents make bad routing worse, not better; a
   fitness agent is useless if a fitness question reaches the coding agent.
2. **The domain needs its own tools or memory shape.** If an agent is only a different
   system prompt, it should be a prompt, not an agent. Splitting on personality rather
   than capability is how agent systems become unmaintainable.
