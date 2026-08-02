import uuid
from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ray.db.base import Base, TimestampMixin, uuid_pk


class User(Base, TimestampMixin):
    """The Ray user.

    V1 seeds exactly one row, but every other table keeps a ``user_id`` foreign key
    so multi-user support is a configuration change rather than a migration
    (ADR-0006).
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    # Communication style, explanation depth, timezone.
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    # Enabled memory categories, provider overrides, voice on/off.
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
