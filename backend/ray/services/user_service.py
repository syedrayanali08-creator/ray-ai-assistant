import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.models import User
from ray.schemas import UserRead


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> UserRead | None:
    user = await session.get(User, user_id)
    return UserRead.model_validate(user) if user is not None else None


async def get_first_user(session: AsyncSession) -> UserRead | None:
    result = await session.execute(select(User).order_by(User.created_at).limit(1))
    user = result.scalar_one_or_none()
    return UserRead.model_validate(user) if user is not None else None
