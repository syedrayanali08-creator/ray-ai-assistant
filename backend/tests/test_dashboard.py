import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.models import CalendarEvent, Memory
from ray.domain.enums import MemoryCategory
from ray.schemas import TaskCreate
from ray.services import memory_service, task_service


async def test_dashboard_returns_every_panel(auth_client: AsyncClient) -> None:
    payload = (await auth_client.get("/dashboard")).json()
    assert set(payload) == {
        "user",
        "projects",
        "tasks",
        "today_events",
        "memories",
        "agents",
        "overdue_count",
    }


async def test_overdue_count_uses_deadlines(
    session: AsyncSession, user_id: uuid.UUID, auth_client: AsyncClient
) -> None:
    now = datetime.now(UTC)
    await task_service.create_task(
        session, user_id, TaskCreate(title="Late", deadline=now - timedelta(days=1))
    )
    await task_service.create_task(
        session, user_id, TaskCreate(title="Soon", deadline=now + timedelta(days=1))
    )
    await session.commit()

    assert (await auth_client.get("/dashboard")).json()["overdue_count"] == 1


async def test_today_events_exclude_other_days(
    session: AsyncSession, user_id: uuid.UUID, auth_client: AsyncClient
) -> None:
    now = datetime.now(UTC)
    session.add_all(
        [
            CalendarEvent(
                user_id=user_id,
                title="Today",
                start_time=now,
                end_time=now + timedelta(hours=1),
            ),
            CalendarEvent(
                user_id=user_id,
                title="Next week",
                start_time=now + timedelta(days=7),
                end_time=now + timedelta(days=7, hours=1),
            ),
        ]
    )
    await session.commit()

    titles = [e["title"] for e in (await auth_client.get("/dashboard")).json()["today_events"]]
    assert titles == ["Today"]


async def test_superseded_memories_are_not_listed(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    old = Memory(
        user_id=user_id,
        category=MemoryCategory.USER,
        content="Uses Java",
        why="early conversation",
    )
    new = Memory(
        user_id=user_id,
        category=MemoryCategory.USER,
        content="Uses Python",
        why="corrected later",
    )
    session.add_all([old, new])
    await session.flush()
    old.superseded_by = new.id
    await session.commit()

    contents = [m.content for m in await memory_service.list_memories(session, user_id)]
    assert contents == ["Uses Python"]
