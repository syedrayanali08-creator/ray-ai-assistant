"""Single-user authentication (ADR-0006).

Everything that identifies the caller happens in ``get_current_user``. Replacing
this one function with a session or OIDC lookup is the whole of the future
multi-user migration — no route, service, or model changes.
"""

import secrets
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ray.config import Settings, get_settings
from ray.db.models import User
from ray.db.session import get_session

_bearer = HTTPBearer(auto_error=False)


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Constant-time comparison: a timing side channel on a local token is cheap to
    # avoid and embarrassing to leave in.
    if not secrets.compare_digest(credentials.credentials, settings.api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_id(
    _: None = Depends(verify_token),
    session: AsyncSession = Depends(get_session),
) -> uuid.UUID:
    """Resolve the caller to a user id.

    V1 has exactly one user row, seeded by ``scripts/seed.py``.
    """
    result = await session.execute(select(User.id).order_by(User.created_at).limit(1))
    user_id = result.scalar_one_or_none()
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No user has been seeded. Run: uv run python scripts/seed.py",
        )
    return user_id
