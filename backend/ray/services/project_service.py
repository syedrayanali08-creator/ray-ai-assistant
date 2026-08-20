import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.models import Project
from ray.domain.enums import ProjectStatus
from ray.schemas import ProjectCreate, ProjectRead, ProjectUpdate


async def list_projects(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: ProjectStatus | None = None,
) -> list[ProjectRead]:
    stmt = select(Project).where(Project.user_id == user_id)
    if status is not None:
        stmt = stmt.where(Project.status == status)
    result = await session.execute(stmt.order_by(Project.updated_at.desc()))
    return [ProjectRead.model_validate(p) for p in result.scalars()]


async def get_project(
    session: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID
) -> ProjectRead | None:
    stmt = select(Project).where(Project.id == project_id, Project.user_id == user_id)
    project = (await session.execute(stmt)).scalar_one_or_none()
    return ProjectRead.model_validate(project) if project is not None else None


async def create_project(
    session: AsyncSession, user_id: uuid.UUID, data: ProjectCreate
) -> ProjectRead:
    project = Project(user_id=user_id, **data.model_dump())
    session.add(project)
    await session.flush()
    return ProjectRead.model_validate(project)


async def update_project(
    session: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID, data: ProjectUpdate
) -> ProjectRead | None:
    stmt = select(Project).where(Project.id == project_id, Project.user_id == user_id)
    project = (await session.execute(stmt)).scalar_one_or_none()
    if project is None:
        return None

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    await session.flush()
    await session.refresh(project)
    return ProjectRead.model_validate(project)


async def delete_project(session: AsyncSession, user_id: uuid.UUID, project_id: uuid.UUID) -> bool:
    stmt = select(Project).where(Project.id == project_id, Project.user_id == user_id)
    project = (await session.execute(stmt)).scalar_one_or_none()
    if project is None:
        return False
    await session.delete(project)
    return True
