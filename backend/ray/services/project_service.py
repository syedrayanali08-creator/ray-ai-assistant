import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.models import Project
from ray.domain.enums import ProjectStatus
from ray.schemas import ProjectRead


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
