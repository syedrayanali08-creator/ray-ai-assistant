import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.models import Project, Task
from ray.domain.enums import TaskStatus
from ray.schemas import TaskCreate, TaskRead, TaskUpdate
from ray.services.errors import UnknownProjectError

# Tasks a project owns and standalone tasks are the same rows (ADR-0004); the only
# difference is whether project_id is set.


async def list_tasks(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: TaskStatus | None = None,
    project_id: uuid.UUID | None = None,
    include_done: bool = False,
) -> list[TaskRead]:
    stmt = select(Task).where(Task.user_id == user_id)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    elif not include_done:
        stmt = stmt.where(Task.status.notin_([TaskStatus.DONE, TaskStatus.CANCELLED]))
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    # Nulls last so undated tasks do not crowd out the ones with deadlines.
    stmt = stmt.order_by(Task.deadline.asc().nullslast(), Task.created_at.asc())
    result = await session.execute(stmt)
    return [TaskRead.model_validate(t) for t in result.scalars()]


async def _assert_project_exists(
    session: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID | None
) -> None:
    if project_id is None:
        return
    stmt = select(Project.id).where(Project.id == project_id, Project.user_id == user_id)
    if (await session.execute(stmt)).scalar_one_or_none() is None:
        raise UnknownProjectError(project_id)


async def create_task(session: AsyncSession, user_id: uuid.UUID, data: TaskCreate) -> TaskRead:
    await _assert_project_exists(session, user_id, data.project_id)
    task = Task(user_id=user_id, **data.model_dump())
    if task.status is TaskStatus.DONE:
        task.completed_at = datetime.now(UTC)
    session.add(task)
    await session.flush()
    return TaskRead.model_validate(task)


async def update_task(
    session: AsyncSession, user_id: uuid.UUID, task_id: uuid.UUID, data: TaskUpdate
) -> TaskRead | None:
    stmt = select(Task).where(Task.id == task_id, Task.user_id == user_id)
    task = (await session.execute(stmt)).scalar_one_or_none()
    if task is None:
        return None

    fields = data.model_dump(exclude_unset=True)
    if "title" in fields:
        task.title = fields["title"]
    if "description" in fields:
        task.description = fields["description"]
    if "project_id" in fields:
        await _assert_project_exists(session, user_id, fields["project_id"])
        task.project_id = fields["project_id"]
    if "status" in fields:
        task.status = fields["status"]
    if "priority" in fields:
        task.priority = fields["priority"]
    if "category" in fields:
        task.category = fields["category"]
    if "deadline" in fields:
        task.deadline = fields["deadline"]

    # completed_at follows status rather than being set by the caller, so the two
    # cannot disagree.
    if data.status is not None:
        task.completed_at = datetime.now(UTC) if data.status is TaskStatus.DONE else None

    await session.flush()
    # updated_at is set by the database, so it has to be read back.
    await session.refresh(task)
    return TaskRead.model_validate(task)


async def delete_task(session: AsyncSession, user_id: uuid.UUID, task_id: uuid.UUID) -> bool:
    stmt = select(Task).where(Task.id == task_id, Task.user_id == user_id)
    task = (await session.execute(stmt)).scalar_one_or_none()
    if task is None:
        return False
    await session.delete(task)
    return True
