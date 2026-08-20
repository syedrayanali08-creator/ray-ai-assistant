"""Calendar API: events, ICS export/import."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.session import get_session
from ray.schemas import CalendarEventCreate, CalendarEventRead, CalendarEventUpdate
from ray.security.auth import get_current_user_id
from ray.services import calendar_service
from ray.services.errors import InvalidEventError

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("", response_model=list[CalendarEventRead])
async def list_events(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[CalendarEventRead]:
    return await calendar_service.list_events(session, user_id, start=start, end=end, limit=limit)


@router.get("/today", response_model=list[CalendarEventRead])
async def today_events(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[CalendarEventRead]:
    now = datetime.now(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return await calendar_service.list_events(
        session, user_id, start=day_start, end=day_start + timedelta(days=1)
    )


@router.get("/export.ics", response_class=PlainTextResponse)
async def export_ics(
    days: int = Query(default=30, ge=1, le=365),
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> str:
    start = datetime.now(UTC)
    events = await calendar_service.list_events(
        session, user_id, start=start, end=start + timedelta(days=days)
    )
    return calendar_service.export_ics(events)


@router.post(
    "/import.ics",
    response_model=list[CalendarEventRead],
    status_code=status.HTTP_201_CREATED,
)
async def import_ics(
    ics_data: str = Body(..., media_type="text/calendar"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[CalendarEventRead]:
    created = []
    for data in calendar_service.import_ics(ics_data):
        try:
            created.append(await calendar_service.create_event(session, user_id, data))
        except InvalidEventError:
            continue
    return created


@router.get("/{event_id}", response_model=CalendarEventRead)
async def get_event(
    event_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> CalendarEventRead:
    event = await calendar_service.get_event(session, user_id, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.post("/event", response_model=CalendarEventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    data: CalendarEventCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> CalendarEventRead:
    try:
        return await calendar_service.create_event(session, user_id, data)
    except InvalidEventError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.patch("/event/{event_id}", response_model=CalendarEventRead)
async def update_event(
    event_id: uuid.UUID,
    data: CalendarEventUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> CalendarEventRead:
    try:
        event = await calendar_service.update_event(session, user_id, event_id, data)
    except InvalidEventError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.delete("/event/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    if not await calendar_service.delete_event(session, user_id, event_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
