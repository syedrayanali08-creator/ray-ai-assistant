# `/docs/08 API and Backend Interface Specification.md`

# Ray — API and Backend Interface Specification

## Purpose

This document defines how Ray's internal systems communicate.

The backend is responsible for:

* receiving user requests
* managing conversations
* coordinating agents
* accessing memory
* managing projects/tasks
* connecting external tools

The API should be modular so new agents and integrations can be added without rebuilding the system.

---

# Backend Architecture

High-level flow:

```
Frontend Dashboard

        ↓

Backend API

        ↓

Ray Core

        ↓

Executive Agent

        ↓

Specialized Agents

        ↓

Tools / Database / Memory
```

---

# API Design Principles

The API should be:

* modular
* documented
* secure
* easy to extend
* free from unnecessary complexity

Approach (ADR-0007):

* **REST for everything.**
* **Server-Sent Events** for streaming chat responses, agent trace events, and approval
  requests. SSE rather than WebSockets because the flow is one-directional and SSE is
  plain HTTP, so it reuses the existing auth and needs no separate connection lifecycle.
* **One WebSocket exception:** `/voice/stream`, which carries microphone audio after
  wake-word activation and is genuinely bidirectional (ADR-0009).

---

# Core API Sections

## 1. Authentication

**V1: single local user, static bearer token (ADR-0006).**

There is no registration or login in V1. One user row is seeded at setup. Every request
outside `/health` must carry:

```
Authorization: Bearer $RAY_API_TOKEN
```

The backend binds to `127.0.0.1` by default. Identity is resolved in exactly one place,
the `get_current_user()` dependency, so real authentication is a single-file
replacement later.

Endpoints:

```
GET /auth/user      -- returns the current user profile and settings
```

### Future (not V1)

If Ray ever becomes multi-user or is exposed beyond localhost, add:

```
POST /auth/register
POST /auth/login
POST /auth/logout
```

backed by OIDC or session cookies. Every table already carries `user_id`, so no schema
change is required.

---

# 2. Conversation API

Purpose:

Handle communication with Ray.

Endpoints:

```
POST /chat/message

GET /chat/history

GET /chat/{conversation_id}
```

Request example:

```json
{
  "message": "Help me plan my week",
  "conversation_id": "123",
  "input_modality": "text",
  "output_modality": "text"
}
```

`POST /chat/message` responds as an **SSE stream** carrying typed events:

```
event: trace     data: {"stage":"routing"}
event: trace     data: {"agent":"coding","memories_used":4}
event: tool      data: {"tool":"github.read_repo","status":"running"}
event: approval  data: {"invocation_id":"...","tool":"calendar.create_event","payload":{...}}
event: token     data: {"text":"Next you should "}
event: done      data: {"message_id":"...","speech_text":"...","trace":{...}}
```

The `trace` object drives the Ray Status panel and the agent visualization, and
satisfies the transparency requirement in `docs/12`. `speech_text` is the spoken variant
of the answer (ADR-0009).

Backend process:

1. Receive message.
2. Retrieve relevant memory.
3. Send request to Executive Agent.
4. Route to required agents.
5. Generate response.
6. Save conversation.

---

# 3. Agent API

Purpose:

Manage Ray's specialized agents.

Endpoints:

Agents are code modules (ADR-0005); this API exposes their runtime state and activity,
not their definitions.

```
GET  /agents                    -- registry entries with enabled state

GET  /agents/{name}

PUT  /agents/{name}             -- enable/disable, user overrides

GET  /agents/activity           -- audit log of what agents did

POST /agents/execute            -- direct invocation, for debugging and tests
```

Example:

Request:

```json
{
  "agent": "coding",
  "task": "Analyze my project"
}
```

In normal operation agents are never called directly by the frontend — the Executive
Agent routes to them (`docs/03`).

Response:

```json
{
  "result": "Project analysis completed"
}
```

---

# 4. Memory API

Purpose:

Manage Ray's memory system.

Endpoints:

```
GET /memory

POST /memory

PUT /memory/{id}

DELETE /memory/{id}

POST /memory/search
```

Example:

Create memory:

```json
{
  "category": "project",
  "content": "User is building Ray"
}
```

---

# 5. Project API

Purpose:

Manage user projects.

Endpoints:

```
GET /projects

POST /projects

GET /projects/{id}

PUT /projects/{id}

DELETE /projects/{id}
```

Project data includes:

* name
* description
* status
* tasks
* technologies
* notes

---

# 6. Task API

Purpose:

Manage tasks.

Endpoints:

```
GET /tasks

POST /tasks

PUT /tasks/{id}

DELETE /tasks/{id}
```

Task fields (one unified model, ADR-0004):

* title
* description
* priority
* deadline
* status
* `project_id` (optional — set means the task belongs to a project)

A project's tasks are fetched with `GET /tasks?project_id=...`. There is no separate
project-task resource.

---

# 7. Calendar API

Purpose:

Manage scheduling.

Endpoints:

```
GET /calendar

POST /calendar/event

PUT /calendar/event/{id}

DELETE /calendar/event/{id}
```

Future support:

* Google Calendar integration
* Notion calendar integration

---

# 8. Integration API

Purpose:

Manage external services.

Endpoints:

```
GET /integrations

POST /integrations/connect

POST /integrations/{id}/check      -- health check, powers self-diagnosis

DELETE /integrations/{id}
```

Examples, in V1 priority order (ADR-0010):

1. GitHub (read-only in V1)
2. Calendar (local default, Google opt-in)
3. Knowledge (Obsidian vault; Notion optional)
4. Local files (allow-listed directories only)

Credentials are never sent to or returned by this API — only a reference to where the
secret is stored.

---

# 9. Approvals API

Purpose:

Gate every side-effecting tool call behind explicit user consent (ADR-0014).

Endpoints:

```
GET  /approvals/pending

POST /approvals/{invocation_id}/approve

POST /approvals/{invocation_id}/reject

GET  /tool-permissions

PUT  /tool-permissions/{tool_name}     -- ask | always_allow | never
```

A pending approval is surfaced mid-stream as an `approval` SSE event; the orchestrator
suspends the tool loop until the decision arrives.

---

# 10. Voice API

Purpose:

Support the voice-first pipeline (ADR-0009).

Endpoints:

```
POST /voice/stt          -- audio -> transcript (faster-whisper, local)

POST /voice/tts          -- text -> audio       (Piper, local)

WS   /voice/stream       -- streamed audio after wake-word activation
```

Wake-word detection runs in the client and never streams audio before activation.

---

# Agent Communication

Agents should not directly modify the database.

Correct flow:

```
Agent

↓

Backend Service

↓

Database
```

This keeps data handling consistent.

---

# AI Request Pipeline

Example:

User:

"Help me continue my Processing game."

Process:

1. Frontend sends message.
2. Backend receives request.
3. Executive Agent analyzes intent.
4. Memory system retrieves:

   * project information
   * previous progress
   * user preferences
5. Coding Agent receives context.
6. Coding Agent generates response.
7. Response returns to frontend.
8. Conversation is stored.

---

# Error Handling

Every API should return clear errors.

Example:

```json
{
  "error": "Calendar integration unavailable",
  "reason": "Authentication expired"
}
```

Ray should explain failures instead of silently failing.

---

# Free Technology Requirement

Backend dependencies should prioritize:

* open-source libraries
* free APIs
* local solutions
* free hosting options

Avoid requiring paid services.

---

# Future API Expansion

Possible additions:

* voice endpoints
* GitHub automation
* browser tools
* file analysis
* automation workflows
* mobile application API

---

# Completion Criteria

The backend API system is complete when:

* frontend can communicate with backend
* agents can be called through the API
* memory can be stored and retrieved
* projects and tasks can be managed
* integrations have a common interface
* new features can be added without restructuring the system
