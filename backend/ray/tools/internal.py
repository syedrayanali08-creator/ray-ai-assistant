"""Tools over Ray's own data (ADR-0010, docs/04).

These are the tools that make the specialists useful before any integration exists:
they read and write the tasks, projects, calendar, memories, and learning records Ray
already owns. Everything external — GitHub, the web, a vault, the file system — is
Phase 5 and arrives as more entries in this list.

Two conventions matter:

* **Schemas are small and unambiguous.** A tool with a vague description or an
  overly broad parameter produces bad calls, and a bad call is the model's most
  expensive failure mode.
* **Handlers return plain JSON-able data.** It goes into a prompt, into a
  ``tool_invocations`` row, and onto the screen, so it has to survive serialisation.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from ray.domain.enums import Proficiency, TaskPriority, TaskStatus
from ray.memory.embeddings import get_embedder
from ray.schemas import CalendarEventCreate, TaskCreate, TaskUpdate
from ray.services import (
    calendar_service,
    learning_service,
    memory_service,
    project_service,
    task_service,
)
from ray.services.errors import ServiceError
from ray.tools.manager import Tool, ToolContext

# JSON Schema fragments reused across tools.
_NO_ARGS: dict[str, object] = {"type": "object", "properties": {}}


def _string(description: str, **extra: object) -> dict[str, object]:
    return {"type": "string", "description": description, **extra}


def _dump(models: list[Any]) -> list[dict[str, object]]:
    """Pydantic models to JSON-safe dicts.

    ``mode="json"`` matters: UUIDs and datetimes have to survive being written to a
    JSONB column and read back into a prompt.
    """
    return [model.model_dump(mode="json") for model in models]


def _uuid(arguments: dict[str, object], key: str) -> uuid.UUID | None:
    raw = arguments.get(key)
    if raw in (None, ""):
        return None
    try:
        return uuid.UUID(str(raw))
    except ValueError as exc:
        raise ServiceError(f"{key} is not a valid id.") from exc


def _when(arguments: dict[str, object], key: str) -> datetime:
    """Parse a model-supplied timestamp.

    Models produce ISO 8601 with and without a timezone. A naive value is read as UTC
    rather than rejected — refusing the call would be technically correct and
    practically useless.
    """
    raw = str(arguments.get(key, "")).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ServiceError(f"{key} must be an ISO 8601 timestamp.") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


# -- tasks -------------------------------------------------------------------


async def _tasks_list(ctx: ToolContext, arguments: dict[str, object]) -> dict[str, object]:
    status = arguments.get("status")
    tasks = await task_service.list_tasks(
        ctx.session,
        ctx.user_id,
        status=TaskStatus(status) if isinstance(status, str) and status else None,
        project_id=_uuid(arguments, "project_id") or ctx.project_id,
    )
    return {"tasks": _dump(tasks), "count": len(tasks)}


async def _tasks_create(ctx: ToolContext, arguments: dict[str, object]) -> dict[str, object]:
    deadline = arguments.get("deadline")
    task = await task_service.create_task(
        ctx.session,
        ctx.user_id,
        TaskCreate(
            title=str(arguments.get("title", "")).strip(),
            description=str(arguments.get("description", "")),
            priority=TaskPriority(str(arguments.get("priority", TaskPriority.MEDIUM))),
            deadline=_when(arguments, "deadline") if deadline else None,
            project_id=_uuid(arguments, "project_id") or ctx.project_id,
        ),
    )
    return {"task": task.model_dump(mode="json")}


async def _tasks_update(ctx: ToolContext, arguments: dict[str, object]) -> dict[str, object]:
    task_id = _uuid(arguments, "task_id")
    if task_id is None:
        raise ServiceError("task_id is required.")
    status = arguments.get("status")
    priority = arguments.get("priority")
    task = await task_service.update_task(
        ctx.session,
        ctx.user_id,
        task_id,
        TaskUpdate(
            status=TaskStatus(status) if isinstance(status, str) and status else None,
            priority=TaskPriority(priority) if isinstance(priority, str) and priority else None,
            title=str(arguments["title"]) if arguments.get("title") else None,
        ),
    )
    if task is None:
        raise ServiceError("That task does not exist.")
    return {"task": task.model_dump(mode="json")}


# -- projects ----------------------------------------------------------------


async def _projects_list(ctx: ToolContext, arguments: dict[str, object]) -> dict[str, object]:
    projects = await project_service.list_projects(ctx.session, ctx.user_id)
    return {"projects": _dump(projects), "count": len(projects)}


async def _projects_get(ctx: ToolContext, arguments: dict[str, object]) -> dict[str, object]:
    project_id = _uuid(arguments, "project_id") or ctx.project_id
    if project_id is None:
        raise ServiceError("project_id is required.")
    project = await project_service.get_project(ctx.session, ctx.user_id, project_id)
    if project is None:
        raise ServiceError("That project does not exist.")
    tasks = await task_service.list_tasks(ctx.session, ctx.user_id, project_id=project_id)
    return {"project": project.model_dump(mode="json"), "open_tasks": _dump(tasks)}


# -- calendar ----------------------------------------------------------------


async def _calendar_list(ctx: ToolContext, arguments: dict[str, object]) -> dict[str, object]:
    days = int(str(arguments.get("days") or 7))
    start = datetime.now(UTC)
    events = await calendar_service.list_events(
        ctx.session, ctx.user_id, start=start, end=start + timedelta(days=days)
    )
    return {"events": _dump(events), "count": len(events), "window_days": days}


async def _calendar_create(ctx: ToolContext, arguments: dict[str, object]) -> dict[str, object]:
    event = await calendar_service.create_event(
        ctx.session,
        ctx.user_id,
        CalendarEventCreate(
            title=str(arguments.get("title", "")).strip(),
            start_time=_when(arguments, "start_time"),
            end_time=_when(arguments, "end_time"),
            description=str(arguments.get("description", "")),
            task_id=_uuid(arguments, "task_id"),
        ),
    )
    return {"event": event.model_dump(mode="json")}


def _describe_event(arguments: dict[str, object]) -> str:
    """The sentence on the approval card: what will exist if the user says yes."""
    title = arguments.get("title", "an event")
    try:
        start = _when(arguments, "start_time")
        end = _when(arguments, "end_time")
    except ServiceError:
        return f"Create the event {title!r}"
    when = start.strftime("%a %d %b %H:%M")
    return f"Create {title!r} on {when} - {end.strftime('%H:%M')}"


# -- memory ------------------------------------------------------------------


async def _memory_search(ctx: ToolContext, arguments: dict[str, object]) -> dict[str, object]:
    """Memory as a tool, not an agent (ADR-0005).

    The orchestrator already retrieves memories for every turn; this exists for the
    case where an agent realises mid-answer that it needs something specific.
    """
    query = str(arguments.get("query", "")).strip()
    if not query:
        raise ServiceError("query is required.")
    embedding = (await get_embedder().embed([query]))[0]
    disabled = await memory_service.disabled_categories(ctx.session, ctx.user_id)
    found = await memory_service.search(
        ctx.session,
        ctx.user_id,
        embedding,
        limit=int(str(arguments.get("limit") or 5)),
        project_id=ctx.project_id,
        exclude_categories=disabled,
    )
    return {
        "memories": [
            {"content": memory.content, "category": memory.category, "score": round(score, 3)}
            for memory, score, _ in found
        ]
    }


# -- learning ----------------------------------------------------------------


async def _learning_get(ctx: ToolContext, arguments: dict[str, object]) -> dict[str, object]:
    topic = str(arguments.get("topic", "")).strip()
    if not topic:
        records = await learning_service.list_records(ctx.session, ctx.user_id)
        return {"records": _dump(records)}
    record = await learning_service.get_record(ctx.session, ctx.user_id, topic)
    # An unknown topic is not an error: "no record" is the answer, and it selects the
    # beginner explanation mode in docs/07.
    return {
        "topic": topic,
        "record": None if record is None else record.model_dump(mode="json"),
        "proficiency": Proficiency.NONE if record is None else record.proficiency,
    }


async def _learning_update(ctx: ToolContext, arguments: dict[str, object]) -> dict[str, object]:
    topic = str(arguments.get("topic", "")).strip()
    if not topic:
        raise ServiceError("topic is required.")
    proficiency = arguments.get("proficiency")
    record = await learning_service.upsert(
        ctx.session,
        ctx.user_id,
        topic=topic,
        proficiency=(
            Proficiency(proficiency) if isinstance(proficiency, str) and proficiency else None
        ),
        strengths=_optional_str(arguments, "strengths"),
        weaknesses=_optional_str(arguments, "weaknesses"),
        notes=_optional_str(arguments, "notes"),
    )
    return {"record": record.model_dump(mode="json")}


def _optional_str(arguments: dict[str, object], key: str) -> str | None:
    value = arguments.get(key)
    return str(value) if isinstance(value, str) and value.strip() else None


async def _feedback_create_improvement_task(
    ctx: ToolContext, arguments: dict[str, object]
) -> dict[str, object]:
    title = str(arguments.get("title", "")).strip()
    if not title:
        raise ServiceError("title is required.")
    workaround = _optional_str(arguments, "workaround") or ""
    description = str(arguments.get("description", "")).strip()
    if workaround:
        description += f"\n\nWorkaround: {workaround}"
    task = await task_service.create_task(
        ctx.session,
        ctx.user_id,
        TaskCreate(
            title=title,
            description=description,
            priority=TaskPriority.HIGH,
            category="improvement",
        ),
    )
    return {"task": task.model_dump(mode="json")}


INTERNAL_TOOLS: tuple[Tool, ...] = (
    Tool(
        name="tasks.list",
        description="List the user's open tasks, optionally filtered by status or project.",
        parameters={
            "type": "object",
            "properties": {
                "status": _string(
                    "Only tasks with this status.",
                    enum=[status.value for status in TaskStatus],
                ),
                "project_id": _string("Only tasks in this project."),
            },
        },
        handler=_tasks_list,
    ),
    Tool(
        name="tasks.create",
        description="Create a task for the user. Use one call per task.",
        parameters={
            "type": "object",
            "properties": {
                "title": _string("Short imperative title."),
                "description": _string("Optional detail."),
                "priority": _string(
                    "How urgent.", enum=[priority.value for priority in TaskPriority]
                ),
                "deadline": _string("ISO 8601 timestamp."),
                "project_id": _string("Project this task belongs to."),
            },
            "required": ["title"],
        },
        handler=_tasks_create,
        side_effect=True,
        summarise=lambda args: f"Create the task {args.get('title', '')!r}",
    ),
    Tool(
        name="tasks.update",
        description="Change a task's status, priority, or title.",
        parameters={
            "type": "object",
            "properties": {
                "task_id": _string("The task to change."),
                "status": _string("New status.", enum=[status.value for status in TaskStatus]),
                "priority": _string(
                    "New priority.", enum=[priority.value for priority in TaskPriority]
                ),
                "title": _string("New title."),
            },
            "required": ["task_id"],
        },
        handler=_tasks_update,
        side_effect=True,
        summarise=lambda args: f"Update task {args.get('task_id', '')}",
    ),
    Tool(
        name="projects.list",
        description="List the user's projects and their status.",
        parameters=_NO_ARGS,
        handler=_projects_list,
    ),
    Tool(
        name="projects.get",
        description="Get one project with its open tasks.",
        parameters={
            "type": "object",
            "properties": {"project_id": _string("The project to read.")},
        },
        handler=_projects_get,
    ),
    Tool(
        name="calendar.list",
        description="List upcoming calendar events.",
        parameters={
            "type": "object",
            "properties": {"days": {"type": "integer", "description": "How far ahead to look."}},
        },
        handler=_calendar_list,
    ),
    Tool(
        name="calendar.create",
        description="Create a calendar event or a time block for a task.",
        parameters={
            "type": "object",
            "properties": {
                "title": _string("What the block is for."),
                "start_time": _string("ISO 8601 start."),
                "end_time": _string("ISO 8601 end."),
                "description": _string("Optional detail."),
                "task_id": _string("Task this block is for."),
            },
            "required": ["title", "start_time", "end_time"],
        },
        handler=_calendar_create,
        side_effect=True,
        summarise=_describe_event,
    ),
    Tool(
        name="memory.search",
        description="Search what Ray remembers about the user.",
        parameters={
            "type": "object",
            "properties": {
                "query": _string("What to look for."),
                "limit": {"type": "integer", "description": "How many memories to return."},
            },
            "required": ["query"],
        },
        handler=_memory_search,
    ),
    Tool(
        name="learning.get",
        description="Read the user's proficiency and notes for a topic. Omit the topic for all.",
        parameters={
            "type": "object",
            "properties": {"topic": _string("The topic to look up.")},
        },
        handler=_learning_get,
    ),
    Tool(
        name="learning.update",
        description="Record what the user now understands about a topic.",
        parameters={
            "type": "object",
            "properties": {
                "topic": _string("The topic taught."),
                "proficiency": _string(
                    "Current level.", enum=[level.value for level in Proficiency]
                ),
                "strengths": _string("What they grasped."),
                "weaknesses": _string("What still needs work."),
                "notes": _string("Anything worth remembering next time."),
            },
            "required": ["topic"],
        },
        handler=_learning_update,
        side_effect=True,
        summarise=lambda args: f"Record progress on {args.get('topic', '')!r}",
    ),
    Tool(
        name="feedback.create_improvement_task",
        description=(
            "Capture something the user finds annoying or wants improved. "
            "Call this when the user says a workflow is annoying, slow, confusing, "
            "or should be easier."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": _string("Short title for the improvement."),
                "description": _string("What the user said and why it matters."),
                "workaround": _string("Any workaround the user already found."),
            },
            "required": ["title"],
        },
        handler=_feedback_create_improvement_task,
        side_effect=True,
        summarise=lambda args: f"Capture improvement: {args.get('title', '')!r}",
    ),
)
