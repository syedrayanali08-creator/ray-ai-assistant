import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ray.db.base import Base, TimestampMixin, uuid_pk
from ray.domain.enums import IntegrationStatus, IntegrationType


class Integration(Base, TimestampMixin):
    __tablename__ = "integrations"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_integration_provider"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[IntegrationType] = mapped_column(nullable=False)
    # Concrete implementation behind the adapter, e.g. "local", "google", "obsidian".
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[IntegrationStatus] = mapped_column(
        default=IntegrationStatus.DISCONNECTED, nullable=False
    )

    # The name of an environment variable or OS keyring key. NEVER a secret value —
    # secrets must not be readable from the database (docs/12).
    credentials_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Non-secret settings: vault path, repo allow-list, calendar id.
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
