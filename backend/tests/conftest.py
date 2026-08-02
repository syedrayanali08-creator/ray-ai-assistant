import os
import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from ray.config import get_settings
from ray.db.base import Base
from ray.db.models import User
from ray.db.session import get_engine, get_sessionmaker
from ray.main import create_app

TEST_TOKEN = "test-token"

# Configure before the settings cache is populated by anything else.
os.environ.setdefault("RAY_API_TOKEN", TEST_TOKEN)
os.environ.setdefault("RAY_DATABASE_URL", "postgresql+asyncpg://ray:ray@localhost:5433/ray_test")


@pytest.fixture(scope="session", autouse=True)
def _settings() -> None:
    get_settings.cache_clear()
    get_settings()


async def _ensure_test_database() -> None:
    """Create the test database if it does not exist.

    Tests must never run against the development database — they drop tables.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    url = get_settings().database_url
    admin_url, _, test_db = url.rpartition("/")
    admin = create_async_engine(f"{admin_url}/postgres", isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": test_db}
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{test_db}"'))
    finally:
        await admin.dispose()


@pytest.fixture(scope="session")
async def _schema() -> AsyncIterator[None]:
    await _ensure_test_database()
    engine = get_engine()
    async with engine.begin() as conn:
        from sqlalchemy import text

        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
async def _clean(_schema: None) -> None:
    """Truncate between tests so each one starts from an empty database."""
    from sqlalchemy import text

    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    async with get_engine().begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def session(_schema: None) -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


@pytest.fixture
async def user(session: AsyncSession) -> User:
    user = User(name="Test User", email="test@example.com", preferences={}, settings={})
    session.add(user)
    await session.commit()
    return user


@pytest.fixture
async def client(_schema: None) -> AsyncIterator[AsyncClient]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def auth_client(client: AsyncClient, user: User) -> AsyncClient:
    """A client that is authenticated and has a seeded user to resolve to."""
    client.headers["Authorization"] = f"Bearer {TEST_TOKEN}"
    return client


@pytest.fixture
def user_id(user: User) -> uuid.UUID:
    return user.id
