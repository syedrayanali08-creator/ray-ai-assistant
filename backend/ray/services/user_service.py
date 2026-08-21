import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.models import User
from ray.schemas import UserRead, UserUpdate


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> UserRead | None:
    user = await session.get(User, user_id)
    return UserRead.model_validate(user) if user is not None else None


async def get_first_user(session: AsyncSession) -> UserRead | None:
    result = await session.execute(select(User).order_by(User.created_at).limit(1))
    user = result.scalar_one_or_none()
    return UserRead.model_validate(user) if user is not None else None


async def update_user(session: AsyncSession, user_id: uuid.UUID, payload: UserUpdate) -> UserRead:
    user = await session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    for field in ("name", "email"):
        value = getattr(payload, field)
        if value is not None:
            setattr(user, field, value)
    if payload.preferences is not None:
        user.preferences = payload.preferences
    if payload.settings is not None:
        user.settings = payload.settings
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)
