"""The conversation endpoint (ADR-0007).

``POST /chat/message`` answers as an SSE stream. Note that the streaming body opens
its *own* database session rather than taking the request-scoped one: FastAPI closes
``yield`` dependencies before the response body is consumed, so a dependency-provided
session would be closed underneath the generator.
"""

import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ray.api.sse import SSE_HEADERS, format_event
from ray.core.contracts import RayRequest
from ray.core.events import ErrorEvent
from ray.core.orchestrator import Orchestrator
from ray.db.session import get_session, get_sessionmaker
from ray.llm.registry import get_registry
from ray.schemas import ChatRequest, ConversationRead, ConversationSummary, ProviderStatus
from ray.security.auth import get_current_user_id
from ray.services import conversation_service, user_service

router = APIRouter(prefix="/chat", tags=["chat"])


def get_orchestrator() -> Orchestrator:
    return Orchestrator()


@router.post("/message")
async def send_message(
    data: ChatRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> StreamingResponse:
    user = await user_service.get_user(session, user_id)
    user_name = user.name if user is not None else "there"

    request = RayRequest(
        user_id=user_id,
        message=data.message,
        conversation_id=data.conversation_id,
        input_modality=data.input_modality,
        output_modality=data.output_modality,
        project_id=data.project_id,
    )

    async def stream() -> AsyncIterator[str]:
        async with get_sessionmaker()() as stream_session:
            try:
                async for event in orchestrator.run(stream_session, request, user_name):
                    yield format_event(event)
            except Exception as exc:
                # The HTTP status was sent when the stream opened, so failures after
                # that point can only be reported in-band.
                await stream_session.rollback()
                yield format_event(
                    ErrorEvent(message=f"Ray hit an unexpected error: {exc}", retryable=False)
                )

    return StreamingResponse(stream(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("/history", response_model=list[ConversationSummary])
async def list_history(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[ConversationSummary]:
    return await conversation_service.list_conversations(session, user_id)


@router.get("/providers", response_model=list[ProviderStatus])
async def list_providers(_: uuid.UUID = Depends(get_current_user_id)) -> list[ProviderStatus]:
    """The provider chain, in order, with the reason anything unusable is unusable."""
    return [
        ProviderStatus(
            name=info.name, model=info.model, configured=info.configured, detail=info.detail
        )
        for info in get_registry().describe()
    ]


@router.get("/{conversation_id}", response_model=ConversationRead)
async def read_conversation(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ConversationRead:
    conversation = await conversation_service.get_conversation(session, user_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    if not await conversation_service.delete_conversation(session, user_id, conversation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
