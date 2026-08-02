# ADR-0004 — One unified Task model

## Status

Accepted. Supersedes the `Task` / `ProjectTask` split in `docs/06`.

## Context

`docs/06` defined two tables with nearly identical fields: `Task` (life tasks, owned by
a user) and `ProjectTask` (owned by a project). Every downstream layer would have had to
duplicate itself: two sets of CRUD services, two API resources, two agent tools, and two
UI list components — and "show me everything due this week" would need a union query
across both.

## Decision

**One `tasks` table with a nullable `project_id`.**

```
Task
- id
- user_id            (required)
- project_id         (nullable — set means the task belongs to a project)
- title
- description
- status             enum: todo | in_progress | blocked | done | cancelled
- priority           enum: low | medium | high | urgent
- category           (free text, e.g. "university", "errand")
- deadline           (nullable, timestamptz)
- completed_at       (nullable)
- created_at / updated_at
```

A project's task list is `WHERE project_id = :id`. A life task is `project_id IS NULL`.
There is one Task service, one `/tasks` API resource, one task tool for the Planning
Agent, and one task UI component that is reused inside the project view.

## Alternatives considered

* **Keep both tables** as originally documented. Rejected: pure duplication with no
  behavioural difference between the two entities.
* **Single-table inheritance with a `type` discriminator.** Same table, but adds a
  column that nothing would branch on — `project_id IS NULL` already carries the
  meaning.

## Consequences

* `docs/06` must be updated to remove `ProjectTask`. Done as part of this change.
* Deleting a project must decide what happens to its tasks: tasks are **not** deleted,
  their `project_id` is set to `NULL` and the project name is preserved in the task
  description context. Losing tasks silently would be a data-loss bug.
