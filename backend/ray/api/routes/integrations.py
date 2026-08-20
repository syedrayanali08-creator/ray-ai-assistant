"""Integration API: manage external service connections."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.session import get_session
from ray.schemas import IntegrationCheck, IntegrationCreate, IntegrationRead, IntegrationUpdate
from ray.security.auth import get_current_user_id
from ray.services import integration_service

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("", response_model=list[IntegrationRead])
async def list_integrations(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[IntegrationRead]:
    return await integration_service.list_integrations(session, user_id)


@router.post("", response_model=IntegrationRead, status_code=status.HTTP_201_CREATED)
async def create_integration(
    data: IntegrationCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> IntegrationRead:
    return await integration_service.create_integration(session, user_id, data)


@router.get("/{integration_id}", response_model=IntegrationRead)
async def get_integration(
    integration_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> IntegrationRead:
    integration = await integration_service.get_integration(session, user_id, integration_id)
    if integration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return integration


@router.patch("/{integration_id}", response_model=IntegrationRead)
async def update_integration(
    integration_id: uuid.UUID,
    data: IntegrationUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> IntegrationRead:
    integration = await integration_service.update_integration(
        session, user_id, integration_id, data
    )
    if integration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return integration


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    if not await integration_service.delete_integration(session, user_id, integration_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")


@router.post("/{integration_id}/check", response_model=IntegrationCheck)
async def check_integration(
    integration_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> IntegrationCheck:
    result = await integration_service.check_integration(session, user_id, integration_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return result
