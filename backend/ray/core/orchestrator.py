"""Ray Core: the pipeline every turn flows through.

It is an async generator rather than a function returning an answer, for two
reasons. Streaming has to be native — bolting it on later would mean buffering the
whole response first. And the trace has to be *recorded* as each step happens, not
reconstructed afterwards or, worse, asked of the model, which would produce a
plausible fiction instead of a fact.

The orchestrator only sequences. Retrieval, prompting, model calls, and persistence
each live elsewhere; when this file starts containing logic, that logic is in the
wrong place.
"""

import time
import uuid
from collections.abc import AsyncIterator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from ray.agents.base import AgentContext, AgentFinished, AgentToken
from ray.agents.executive import ExecutiveAgent
from ray.config import Settings, get_settings
from ray.core.contracts import RayRequest, TraceEvent, TraceStage
from ray.core.events import DoneEvent, ErrorEvent, StreamEvent, TokenEvent, TraceStreamEvent
from ray.domain.enums import MessageRole
from ray.llm.base import LLMError
from ray.llm.registry import Degradation, ProviderRegistry, get_registry
from ray.memory.retrieval import NullRetriever, Retriever
from ray.services import activity_service, conversation_service

log = structlog.get_logger()


class Orchestrator:
    def __init__(
        self,
        *,
        providers: ProviderRegistry | None = None,
        retriever: Retriever | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._providers = providers or get_registry()
        # Phase 3 swaps this for the real retriever; nothing else changes.
        self._retriever = retriever or NullRetriever()

    async def run(
        self, session: AsyncSession, request: RayRequest, user_name: str
    ) -> AsyncIterator[StreamEvent]:
        started = time.perf_counter()
        trace: list[TraceEvent] = []

        def record(stage: TraceStage, **detail: object) -> TraceStreamEvent:
            trace.append(TraceEvent(stage=stage, detail=detail))
            return TraceStreamEvent(stage=stage, detail=detail)

        conversation = await conversation_service.get_or_create(
            session, request.user_id, request.conversation_id, first_message=request.message
        )
        # Persisted before the model is called: if the provider dies, what the user
        # said is still in the conversation.
        await conversation_service.add_message(
            session,
            conversation.id,
            role=MessageRole.USER,
            content=request.message,
            input_modality=request.input_modality,
        )
        await session.commit()

        history = await conversation_service.history_for_model(
            session, conversation.id, window=self._settings.history_window
        )
        # The turn being answered is passed to the agent separately; drop its echo.
        history = history[:-1]

        memories = await self._retriever.retrieve(
            request.user_id, request.message, project_id=request.project_id
        )
        yield record("memory", count=len(memories))

        # Phase 4 replaces this constant with a routing call (ADR-0005).
        degradations: list[Degradation] = []
        agent = ExecutiveAgent(
            self._providers,
            temperature=self._settings.llm_temperature,
            on_degrade=degradations.append,
        )
        yield record("routing", agent=agent.name, mode="single-agent")

        ctx = AgentContext(
            user_id=request.user_id,
            user_name=user_name,
            message=request.message,
            history=history,
            memories=memories,
            output_modality=request.output_modality,
            project_id=request.project_id,
        )
        yield record("agent", agent=agent.name, provider=self._providers.chain()[0])

        content = ""
        speech_text = ""
        try:
            async for event in agent.run(ctx):
                if isinstance(event, AgentToken):
                    yield TokenEvent(text=event.text)
                elif isinstance(event, AgentFinished):
                    content = event.content
                    speech_text = event.speech_text
        except LLMError as exc:
            # A provider failure is a message to the user, not a stack trace. The
            # user's turn is already saved, so the conversation stays usable.
            log.warning("orchestrator.provider_failed", error=str(exc), provider=exc.provider)
            await self._finish_activity(
                session, request, conversation.id, agent.name, started, success=False
            )
            yield ErrorEvent(
                message=f"{exc.provider or 'The model provider'} could not answer: {exc}",
                retryable=exc.is_retryable,
            )
            return

        for degradation in degradations:
            # Visible degradation, not silent: the user should know when the answer
            # came from the fallback (ADR-0001).
            yield record(
                "compose", degraded_from=degradation.failed_provider, reason=degradation.reason
            )

        duration_ms = int((time.perf_counter() - started) * 1000)
        yield record("compose", duration_ms=duration_ms, spoken_chars=len(speech_text))

        message = await conversation_service.add_message(
            session,
            conversation.id,
            role=MessageRole.ASSISTANT,
            content=content,
            speech_text=speech_text,
            agent_name=agent.name,
            trace={"events": [{"stage": e.stage, **e.detail} for e in trace]},
        )
        await self._finish_activity(
            session, request, conversation.id, agent.name, started, success=True
        )

        yield DoneEvent(
            conversation_id=conversation.id,
            message_id=message.id,
            agent_name=agent.name,
            speech_text=speech_text,
            duration_ms=duration_ms,
        )

    async def _finish_activity(
        self,
        session: AsyncSession,
        request: RayRequest,
        conversation_id: uuid.UUID,
        agent_name: str,
        started: float,
        *,
        success: bool,
    ) -> None:
        await activity_service.record_activity(
            session,
            user_id=request.user_id,
            conversation_id=conversation_id,
            agent_name=agent_name,
            action="respond",
            summary=request.message,
            duration_ms=int((time.perf_counter() - started) * 1000),
            success=success,
        )
        await session.commit()
