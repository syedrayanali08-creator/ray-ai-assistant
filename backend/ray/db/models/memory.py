import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from ray.config import get_settings
from ray.db.base import Base, TimestampMixin, uuid_pk
from ray.domain.enums import MemoryCategory, MemorySource

EMBEDDING_DIM = get_settings().embedding_dim


class Memory(Base, TimestampMixin):
    """Long-term knowledge with provenance and a local embedding (ADR-0003, ADR-0013)."""

    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[MemoryCategory] = mapped_column(nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[int] = mapped_column(SmallInteger, default=3, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )

    source: Mapped[MemorySource] = mapped_column(default=MemorySource.CONVERSATION, nullable=False)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    # One-line justification, surfaced in the memory dashboard so the user can see
    # why Ray believes something.
    why: Mapped[str] = mapped_column(Text, default="", nullable=False)

    hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # A merged memory supersedes rather than deletes its predecessor, keeping the
    # history auditable (ADR-0013).
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memories.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index(
            "ix_memories_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
