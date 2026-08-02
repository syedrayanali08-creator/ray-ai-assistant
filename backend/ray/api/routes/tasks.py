import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.session import get_session
from ray.domain.enums import TaskStatus
from ray.schemas import TaskCreate, TaskRead, TaskUpdate
from ray.security.auth import get_current_user_id
from ray.services import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    # A project's tasks are just tasks filtered by project (ADR-0004).
    project_id: uuid.UUID | None = None,
    include_done: bool = False,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[TaskRead]:
    return await task_service.list_tasks(
        session,
        user_id,
        status=task_status,
        project_id=project_id,
        include_done=include_done,
    )


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: TaskCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> TaskRead:
    return await task_service.create_task(session, user_id, data)


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> TaskRead:
    task = await task_service.update_task(session, user_id, task_id, data)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    if not await task_service.delete_task(session, user_id, task_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
