"""Ray's FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ray.api.routes import agents, dashboard, health, projects, tasks, user
from ray.config import get_settings
from ray.db.session import dispose_engine
from ray.security.auth import verify_token

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    log.info("ray.startup", env=settings.env, llm_provider=settings.llm_provider)
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Ray API",
        version="0.1.0",
        description="Personal AI assistant backend.",
        lifespan=lifespan,
        # Hide the interactive docs outside development: Ray is a personal service,
        # not a public API.
        docs_url="/docs" if settings.is_development else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)

    # Everything else is authenticated. Applying the dependency here rather than
    # per-route means a new router cannot accidentally ship unprotected
    # (ADR-0006).
    protected = [Depends(verify_token)]
    app.include_router(user.router, dependencies=protected)
    app.include_router(dashboard.router, dependencies=protected)
    app.include_router(projects.router, dependencies=protected)
    app.include_router(tasks.router, dependencies=protected)
    app.include_router(agents.router, dependencies=protected)

    return app


app = create_app()
