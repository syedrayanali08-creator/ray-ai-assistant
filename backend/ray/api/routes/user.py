import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.session import get_session
from ray.schemas import UserRead
from ray.security.auth import get_current_user_id
from ray.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/user", response_model=UserRead)
async def read_current_user(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    user = await user_service.get_user(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
