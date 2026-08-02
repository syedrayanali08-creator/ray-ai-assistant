import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ray.db.base import Base, TimestampMixin, uuid_pk
from ray.domain.enums import MessageRole, Modality


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), default="New conversation", nullable=False)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Spoken variant of the answer. A good spoken response is shorter and contains
    # no code blocks, so it is generated alongside the markdown rather than derived
    # from it (ADR-0009).
    speech_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Agents, tools, memories, and timings — drives the HUD and the transparency
    # requirement in docs/12.
    trace: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    input_modality: Mapped[Modality] = mapped_column(default=Modality.TEXT, nullable=False)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
