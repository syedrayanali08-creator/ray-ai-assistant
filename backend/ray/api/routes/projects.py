"""Project API with full CRUD and progress tracking."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.session import get_session
from ray.schemas import ProjectCreate, ProjectRead, ProjectUpdate
from ray.security.auth import get_current_user_id
from ray.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectRead]:
    return await project_service.list_projects(session, user_id)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ProjectRead:
    project = await project_service.get_project(session, user_id, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ProjectRead:
    return await project_service.create_project(session, user_id, data)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ProjectRead:
    project = await project_service.update_project(session, user_id, project_id, data)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    if not await project_service.delete_project(session, user_id, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
