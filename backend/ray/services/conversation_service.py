"""Conversation and message persistence.

The database boundary for chat: the orchestrator sequences, this module stores.
"""

import uuid
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.models import Conversation, Message
from ray.domain.enums import MessageRole, Modality
from ray.llm.base import LLMMessage
from ray.schemas import ConversationRead, ConversationSummary, MessageRead

# A title is a glance-value label, not a summary.
TITLE_MAX_CHARS = 60


def _title_from(text: str) -> str:
    first_line = text.strip().splitlines()[0] if text.strip() else "New conversation"
    if len(first_line) <= TITLE_MAX_CHARS:
        return first_line
    return f"{first_line[: TITLE_MAX_CHARS - 1].rstrip()}…"


async def get_or_create(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    *,
    first_message: str,
) -> Conversation:
    """Resolve the conversation this turn belongs to.

    An unknown or someone else's id is treated as absent rather than as an error:
    the alternative is losing the user's message to a 404.
    """
    if conversation_id is not None:
        existing = await session.get(Conversation, conversation_id)
        if existing is not None and existing.user_id == user_id:
            return existing

    conversation = Conversation(user_id=user_id, title=_title_from(first_message))
    session.add(conversation)
    await session.flush()
    return conversation


async def add_message(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    role: MessageRole,
    content: str,
    speech_text: str | None = None,
    agent_name: str | None = None,
    trace: dict[str, Any] | None = None,
    input_modality: Modality = Modality.TEXT,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        speech_text=speech_text,
        agent_name=agent_name,
        trace=trace,
        input_modality=input_modality,
    )
    session.add(message)
    await session.flush()
    return message


async def history_for_model(
    session: AsyncSession, conversation_id: uuid.UUID, *, window: int
) -> list[LLMMessage]:
    """The last ``window`` turns, oldest first.

    Selected newest-first and reversed so a long conversation does not load
    entirely into memory just to discard the beginning.
    """
    stmt = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.role.in_([MessageRole.USER, MessageRole.ASSISTANT]),
        )
        .order_by(desc(Message.created_at))
        .limit(window)
    )
    rows = list((await session.execute(stmt)).scalars())
    rows.reverse()
    return [
        LLMMessage(
            role="user" if row.role is MessageRole.USER else "assistant",
            content=row.content,
        )
        for row in rows
    ]


async def list_conversations(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int = 50
) -> list[ConversationSummary]:
    message_count = (
        select(func.count(Message.id))
        .where(Message.conversation_id == Conversation.id)
        .scalar_subquery()
    )
    last_at = (
        select(func.max(Message.created_at))
        .where(Message.conversation_id == Conversation.id)
        .scalar_subquery()
    )
    stmt = (
        select(Conversation, message_count, last_at)
        .where(Conversation.user_id == user_id)
        # Recently *used*, not recently created: a revisited conversation is the
        # one the user is most likely to want next.
        .order_by(desc(func.coalesce(last_at, Conversation.created_at)))
        .limit(limit)
    )
    return [
        ConversationSummary(
            id=conversation.id,
            title=conversation.title,
            message_count=count,
            created_at=conversation.created_at,
            last_message_at=last,
        )
        for conversation, count, last in (await session.execute(stmt)).all()
    ]


async def get_conversation(
    session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> ConversationRead | None:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        return None
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = [MessageRead.model_validate(m) for m in (await session.execute(stmt)).scalars()]
    return ConversationRead(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        messages=messages,
    )


async def delete_conversation(
    session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> bool:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        return False
    await session.delete(conversation)
    return True
