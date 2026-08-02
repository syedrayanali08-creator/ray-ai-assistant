# Ray — Database and Data Model

## Purpose

This document defines how Ray stores and organizes information.

The database supports:

* user memory
* conversations
* projects
* tasks
* calendar events
* agent activity
* tool invocations and approvals
* integrations
* learning progress

The design should remain flexible as Ray gains more capabilities.

> **Decisions applied:** ADR-0002 (PostgreSQL + pgvector as the single store),
> ADR-0004 (one unified Task model), ADR-0005 (agents are code, the database stores
> runtime state only), ADR-0006 (single local user), ADR-0013 (memory policy),
> ADR-0014 (approval gate).

---

# Database Technology

**PostgreSQL 16 with the `pgvector` extension**, run locally through `docker-compose`.

Reasons:

* open-source and free
* handles both relational data and vector search in one system, so a memory query can
  filter by project and rank by similarity in a single statement
* strong ecosystem, migrations, and constraints
* the same engine scales unchanged if Ray ever becomes multi-user

Full reasoning and the rejected alternatives (SQLite + sqlite-vec, a separate vector
database) are in ADR-0002.

Schema changes are managed with **Alembic** migrations from the first table onward
(ADR-0012).

---

# Core Data Model

```
User
 |
 +--- Memories            (vector-searchable long-term knowledge)
 +--- Projects
 |      +--- Tasks        (tasks may also exist without a project)
 +--- Tasks
 +--- Calendar Events
 +--- Conversations
 |      +--- Messages
 +--- Learning Records
 +--- Integrations
 +--- Agent Configs / Agent Activity
 +--- Tool Invocations    (including approvals)
```

Every user-owned table carries a `user_id` foreign key even though V1 has exactly one
user. This keeps multi-user support a configuration change rather than a migration of
every table (ADR-0006).

---

# Tables

## 1. users

Stores the user profile and system preferences.

```
users
- id                uuid pk
- name              text
- email             text (nullable in V1)
- preferences       jsonb   -- communication style, explanation depth, timezone
- settings          jsonb   -- enabled memory categories, default LLM provider, voice on/off
- created_at        timestamptz
- updated_at        timestamptz
```

V1 seeds exactly one row.

---

## 2. memories

Long-term knowledge. This is the table that makes Ray more than a chatbot.

```
memories
- id                uuid pk
- user_id           uuid fk -> users
- category          enum: user | project | learning | goal | conversation
- content           text
- importance        smallint (1-5)
- embedding         vector(384)          -- ADR-0003, HNSW index
- project_id        uuid fk -> projects (nullable, scopes a memory to a project)
- source            enum: conversation | user | tool
- source_message_id uuid fk -> messages (nullable)
- why               text                 -- one-line justification, shown in the UI
- hit_count         integer default 0    -- retrieval count, feeds ranking
- last_used_at      timestamptz (nullable)
- superseded_by     uuid fk -> memories (nullable)
- created_at / updated_at
```

Notes:

* `embedding` is 384-dimensional because Ray embeds locally with `all-MiniLM-L6-v2`
  (ADR-0003). The dimension is asserted against the model at startup.
* `superseded_by` implements the merge path in the dedupe policy — an outdated memory is
  superseded, not destroyed, so the history stays auditable.
* `why` and `source_message_id` are what let the memory dashboard answer "why does Ray
  believe this?".
* Write triggers, deduplication thresholds, and the retrieval scoring formula are
  specified in ADR-0013.

Example:

```
category:   project
content:    User is building a Processing Java game called Starfall Sprint.
importance: 4
source:     conversation
why:        Stated while asking for the next development step; scopes Coding Agent context.
```

---

## 3. projects

```
projects
- id                uuid pk
- user_id           uuid fk -> users
- name              text
- description       text
- status            enum: planning | active | paused | complete | archived
- technology_stack  text[]
- goals             jsonb
- progress          smallint (0-100, nullable)
- repo_url          text (nullable, links the project to a GitHub repository)
- created_at / updated_at
```

---

## 4. tasks

**One table for all tasks.** A task optionally belongs to a project (ADR-0004).

```
tasks
- id                uuid pk
- user_id           uuid fk -> users
- project_id        uuid fk -> projects (nullable)
- title             text
- description       text
- status            enum: todo | in_progress | blocked | done | cancelled
- priority          enum: low | medium | high | urgent
- category          text (nullable, e.g. "university", "errand")
- deadline          timestamptz (nullable)
- completed_at      timestamptz (nullable)
- created_at / updated_at
```

* A project's tasks are `WHERE project_id = :id`.
* A general life task has `project_id IS NULL`.
* Deleting a project sets its tasks' `project_id` to `NULL`; tasks are never deleted
  implicitly.

---

## 5. calendar_events

```
calendar_events
- id                uuid pk
- user_id           uuid fk -> users
- title             text
- description       text
- start_time        timestamptz
- end_time          timestamptz
- location          text (nullable)
- source            enum: ray | google | ics | notion
- external_id       text (nullable, id in the external system)
- task_id           uuid fk -> tasks (nullable, for time-blocked tasks)
- created_at / updated_at
```

`source` and `external_id` allow the local calendar and a synced external calendar to
coexist without duplication (ADR-0010).

---

## 6. conversations

```
conversations
- id                uuid pk
- user_id           uuid fk -> users
- title             text (auto-generated from the first exchange)
- created_at / updated_at
```

---

## 7. messages

```
messages
- id                uuid pk
- conversation_id   uuid fk -> conversations
- role              enum: user | assistant | system | tool
- content           text                 -- markdown, for the screen
- speech_text       text (nullable)      -- spoken variant, ADR-0009
- agent_name        text (nullable)      -- which agent produced an assistant message
- trace             jsonb (nullable)     -- agents, tools, memories used, timings
- input_modality    enum: text | voice
- created_at
```

`trace` is what the Ray Status panel and agent visualization render, and it satisfies
the transparency requirement in `docs/12`.

---

## 8. learning_records

```
learning_records
- id                uuid pk
- user_id           uuid fk -> users
- topic             text
- category          text
- proficiency       enum: none | beginner | intermediate | advanced
- strengths         text (nullable)
- weaknesses        text (nullable)
- notes             text (nullable)
- last_reviewed     timestamptz (nullable)
- created_at / updated_at
```

`proficiency` directly selects the explanation mode in `docs/07` (Beginner /
Intermediate / Advanced), rather than the mode being guessed per conversation.

---

## 9. agent_configs

Runtime state for agents that are defined **in code** (ADR-0005). No prompts or
behaviour are stored here.

```
agent_configs
- id                uuid pk
- user_id           uuid fk -> users
- agent_name        text        -- matches the code-side registry key
- enabled           boolean default true
- user_overrides    jsonb       -- e.g. preferred verbosity for this agent
- updated_at
```

---

## 10. agent_activity

```
agent_activity
- id                uuid pk
- user_id           uuid fk -> users
- agent_name        text
- conversation_id   uuid fk -> conversations (nullable)
- action            text
- tools_used        text[]
- memories_used     uuid[]
- result_summary    text
- duration_ms       integer
- created_at
```

Purpose: let Ray explain exactly what it did, and let the user audit it.

Example:

```
agent_name:     coding
action:         Analyzed repository starfall-sprint
tools_used:     {github.read_repo}
result_summary: Identified 3 candidate next features
duration_ms:    2140
```

---

## 11. tool_invocations

Every tool call, including the approval lifecycle (ADR-0014).

```
tool_invocations
- id                uuid pk
- user_id           uuid fk -> users
- conversation_id   uuid fk -> conversations (nullable)
- tool_name         text
- payload           jsonb        -- exactly what was shown to the user for approval
- side_effect       boolean
- status            enum: pending_approval | approved | rejected | executed | failed
- result            jsonb (nullable)
- error             text (nullable)
- decided_at        timestamptz (nullable)
- created_at
```

A side-effecting tool cannot execute without a row here reaching `approved`.

---

## 12. tool_permissions

Standing approvals and per-tool permission state.

```
tool_permissions
- id                uuid pk
- user_id           uuid fk -> users
- tool_name         text
- mode              enum: ask | always_allow | never
- created_at / updated_at
```

`always_allow` is not permitted for tools that write outside Ray's own database
(GitHub writes, file writes) — those always ask.

---

## 13. integrations

```
integrations
- id                     uuid pk
- user_id                uuid fk -> users
- type                   enum: github | calendar | knowledge | files
- provider               text        -- github | google | local | ics | obsidian | notion
- config                 jsonb       -- non-secret settings, e.g. vault path, allow-listed dirs
- credentials_reference  text        -- env var name or OS keyring key. NEVER a secret value.
- status                 enum: connected | disconnected | error
- last_error             text (nullable)
- last_checked_at        timestamptz (nullable)
- created_at / updated_at
```

**Credentials are never stored in this table.** Only a reference to where the secret
lives (an environment variable name or an OS keyring entry) is stored, per `docs/12`.

---

# Data Relationships

* User → Memories, Projects, Tasks, Calendar Events, Conversations, Learning Records,
  Integrations (one-to-many)
* Project → Tasks (one-to-many, optional from the task side)
* Conversation → Messages (one-to-many)
* Message → Memories (a memory may cite the message it came from)
* Task → Calendar Event (a task may be time-blocked into an event)

---

# Data Storage Rules

## Do

* store information that changes future behaviour
* keep relationships explicit with foreign keys
* keep an audit trail for agent actions and tool calls
* make every deletion user-initiated

## Avoid

* storing every message as a memory (see ADR-0013)
* duplicating structured data (tasks, projects) into prose memories
* storing secrets anywhere in the database
* silent deletion of user data

---

# Future Database Expansion

* knowledge graph over memories
* document storage and file metadata
* AI-generated project summaries
* automation workflow definitions
* multi-user tenancy (already schema-compatible)

---

# Completion Criteria

The database system is complete when:

* Ray can store user information, projects, tasks, events, and conversations
* memories are stored with embeddings, provenance, and importance
* semantic + filtered retrieval runs as a single query
* agent activity and tool invocations are fully auditable
* integrations are described without storing credentials
* new agents and tools can be added without schema restructuring
