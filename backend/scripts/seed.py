"""Seed the single local user and a small amount of realistic starter data.

Idempotent: re-running it will not create a second user or duplicate rows, so it
is safe to run after every migration.

Usage:
    uv run python scripts/seed.py
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ray.config import get_settings
from ray.db.models import CalendarEvent, LearningRecord, Memory, Project, Task, User
from ray.db.session import dispose_engine, get_sessionmaker
from ray.domain.enums import (
    MemoryCategory,
    MemorySource,
    Proficiency,
    ProjectStatus,
    TaskPriority,
    TaskStatus,
)


async def seed_user(session: AsyncSession) -> User:
    settings = get_settings()
    existing = (await session.execute(select(User).limit(1))).scalar_one_or_none()
    if existing is not None:
        print(f"User already exists: {existing.name} ({existing.id})")
        return existing

    user = User(
        name=settings.user_name,
        email=settings.user_email,
        preferences={
            "timezone": settings.user_timezone,
            # Drives the teaching mode in docs/07.
            "explanation_style": "concept_first",
            "tone": "direct",
        },
        settings={
            "enabled_memory_categories": [c.value for c in MemoryCategory],
            "voice_enabled": False,
        },
    )
    session.add(user)
    await session.flush()
    print(f"Created user: {user.name} ({user.id})")
    return user


async def seed_examples(session: AsyncSession, user: User) -> None:
    """Starter rows so the dashboard is not empty on first run.

    Only inserted when the user has no projects — this must never overwrite real
    data.
    """
    has_projects = (
        await session.execute(select(Project.id).where(Project.user_id == user.id).limit(1))
    ).scalar_one_or_none()
    if has_projects is not None:
        print("Example data already present, skipping.")
        return

    now = datetime.now(UTC)

    project = Project(
        user_id=user.id,
        name="Ray",
        description="This assistant. Voice-first, memory-backed, agent-routed.",
        status=ProjectStatus.ACTIVE,
        technology_stack=["Python", "FastAPI", "PostgreSQL", "Next.js", "TypeScript"],
        goals={"current": "Finish Phase 1 foundation", "next": "Core AI conversation"},
        progress=15,
    )
    session.add(project)
    await session.flush()

    session.add_all(
        [
            Task(
                user_id=user.id,
                project_id=project.id,
                title="Wire the dashboard to the live API",
                description="Replace placeholder panels with data from /dashboard.",
                status=TaskStatus.IN_PROGRESS,
                priority=TaskPriority.HIGH,
                category="ray",
                deadline=now + timedelta(days=2),
            ),
            Task(
                user_id=user.id,
                project_id=project.id,
                title="Implement the LLM provider abstraction",
                description="ADR-0001: Gemini default, Ollama fallback.",
                priority=TaskPriority.HIGH,
                category="ray",
                deadline=now + timedelta(days=5),
            ),
            # A standalone task: project_id stays null (ADR-0004).
            Task(
                user_id=user.id,
                title="Review calculus notes",
                priority=TaskPriority.MEDIUM,
                category="university",
                deadline=now + timedelta(days=1),
            ),
        ]
    )

    session.add(
        CalendarEvent(
            user_id=user.id,
            title="Deep work: Ray Phase 1",
            description="Time block created from the Ray project.",
            start_time=now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1),
            end_time=now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=3),
        )
    )

    # Embeddings are null until Phase 3 adds the local embedder (ADR-0003).
    session.add_all(
        [
            Memory(
                user_id=user.id,
                category=MemoryCategory.USER,
                content="Prefers concept explanations before seeing any code.",
                importance=5,
                source=MemorySource.USER,
                why="Stated directly when setting up Ray.",
            ),
            Memory(
                user_id=user.id,
                category=MemoryCategory.PROJECT,
                content="Ray is built with FastAPI, PostgreSQL + pgvector, and Next.js.",
                importance=4,
                project_id=project.id,
                source=MemorySource.USER,
                why="Recorded from the architecture decisions in docs/adr.",
            ),
            Memory(
                user_id=user.id,
                category=MemoryCategory.GOAL,
                content="Wants Ray to be portfolio-quality, not a throwaway prototype.",
                importance=5,
                source=MemorySource.USER,
                why="Primary goal given at project start.",
            ),
        ]
    )

    session.add(
        LearningRecord(
            user_id=user.id,
            topic="System design",
            category="software-engineering",
            proficiency=Proficiency.BEGINNER,
            weaknesses="Choosing between competing storage designs.",
        )
    )

    print("Seeded example project, tasks, event, memories, and a learning record.")


async def main() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        user = await seed_user(session)
        await seed_examples(session, user)
        await session.commit()
    await dispose_engine()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
