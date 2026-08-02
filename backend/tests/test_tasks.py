"""The unified task model is the decision most likely to be quietly broken later
by re-introducing a project-task split, so its behaviour is pinned here (ADR-0004).
"""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.models import Project
from ray.domain.enums import TaskStatus
from ray.schemas import TaskCreate, TaskUpdate
from ray.services import task_service


async def test_task_without_a_project_is_valid(session: AsyncSession, user_id: uuid.UUID) -> None:
    task = await task_service.create_task(
        session, user_id, TaskCreate(title="Buy groceries", category="errand")
    )
    assert task.project_id is None
    await session.commit()


async def test_project_tasks_are_the_same_rows_filtered(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    project = Project(user_id=user_id, name="Starfall Sprint")
    session.add(project)
    await session.flush()

    await task_service.create_task(session, user_id, TaskCreate(title="Standalone"))
    await task_service.create_task(
        session, user_id, TaskCreate(title="Mouse aiming", project_id=project.id)
    )
    await session.commit()

    all_tasks = await task_service.list_tasks(session, user_id)
    project_tasks = await task_service.list_tasks(session, user_id, project_id=project.id)

    assert len(all_tasks) == 2
    assert [t.title for t in project_tasks] == ["Mouse aiming"]


async def test_completing_a_task_sets_completed_at(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    task = await task_service.create_task(session, user_id, TaskCreate(title="Ship Phase 1"))
    assert task.completed_at is None

    done = await task_service.update_task(
        session, user_id, task.id, TaskUpdate(status=TaskStatus.DONE)
    )
    assert done is not None and done.completed_at is not None

    # Reopening must clear it, or "completed" and "todo" would disagree.
    reopened = await task_service.update_task(
        session, user_id, task.id, TaskUpdate(status=TaskStatus.TODO)
    )
    assert reopened is not None and reopened.completed_at is None
    await session.commit()


async def test_deleting_a_project_keeps_its_tasks(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    project = Project(user_id=user_id, name="Doomed")
    session.add(project)
    await session.flush()
    await task_service.create_task(
        session, user_id, TaskCreate(title="Survivor", project_id=project.id)
    )
    await session.commit()

    await session.delete(project)
    await session.commit()

    tasks = await task_service.list_tasks(session, user_id)
    assert [(t.title, t.project_id) for t in tasks] == [("Survivor", None)]


async def test_done_tasks_are_hidden_by_default(session: AsyncSession, user_id: uuid.UUID) -> None:
    task = await task_service.create_task(session, user_id, TaskCreate(title="Old thing"))
    await task_service.update_task(session, user_id, task.id, TaskUpdate(status=TaskStatus.DONE))
    await session.commit()

    assert await task_service.list_tasks(session, user_id) == []
    assert len(await task_service.list_tasks(session, user_id, include_done=True)) == 1


async def test_task_crud_over_the_api(auth_client: AsyncClient) -> None:
    created = await auth_client.post("/tasks", json={"title": "From the API"})
    assert created.status_code == 201
    task_id = created.json()["id"]

    updated = await auth_client.patch(f"/tasks/{task_id}", json={"priority": "urgent"})
    assert updated.status_code == 200
    assert updated.json()["priority"] == "urgent"

    assert (await auth_client.delete(f"/tasks/{task_id}")).status_code == 204
    assert (await auth_client.get("/tasks")).json() == []


async def test_updating_a_missing_task_is_404(auth_client: AsyncClient) -> None:
    response = await auth_client.patch(f"/tasks/{uuid.uuid4()}", json={"title": "ghost"})
    assert response.status_code == 404


async def test_unknown_project_is_404_not_500(auth_client: AsyncClient) -> None:
    # A bad project id must not reach the foreign key constraint.
    ghost = str(uuid.uuid4())
    created = await auth_client.post("/tasks", json={"title": "orphan", "project_id": ghost})
    assert created.status_code == 404

    task_id = (await auth_client.post("/tasks", json={"title": "real"})).json()["id"]
    moved = await auth_client.patch(f"/tasks/{task_id}", json={"project_id": ghost})
    assert moved.status_code == 404
