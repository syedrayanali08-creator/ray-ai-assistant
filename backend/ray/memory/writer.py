"""The write path: extract, embed, dedupe, merge, store (ADR-0013).

The interesting part is not the insert, it is the three-way decision against what
Ray already knows. Without it the store fills with fifty near-identical rows saying
the user is building a Processing game, and retrieval quality collapses — the exact
failure "useful over complete" in `docs/05` is about.

```
similarity ≥ 0.95  →  duplicate: bump the existing row's usage, store nothing
0.85 ≤ sim < 0.95  →  update: write the merged text, supersede the old row
similarity < 0.85  →  new: insert
```
"""

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from ray.config import Settings, get_settings
from ray.domain.enums import MemoryCategory
from ray.memory.embeddings import TextEmbedder, get_embedder
from ray.memory.extraction import MemoryCandidate, MemoryExtractor, forced_candidate
from ray.memory.scoring import DUPLICATE_THRESHOLD, MERGE_THRESHOLD
from ray.services import memory_service

log = structlog.get_logger()

Outcome = str  # "inserted" | "merged" | "duplicate" | "skipped"


@dataclass(frozen=True)
class WriteResult:
    """What the write path did, for the trace and for the tests."""

    inserted: int = 0
    merged: int = 0
    duplicates: int = 0
    memory_ids: tuple[uuid.UUID, ...] = ()

    @property
    def written(self) -> int:
        return self.inserted + self.merged


class MemoryWriter:
    def __init__(
        self,
        extractor: MemoryExtractor,
        *,
        embedder: TextEmbedder | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._extractor = extractor
        self._embedder = embedder or get_embedder()
        self._settings = settings or get_settings()

    async def write_exchange(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        *,
        user_message: str,
        assistant_message: str,
        source_message_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
    ) -> WriteResult:
        """Learn from one exchange. Never raises into the caller.

        This runs after the response has been streamed, so an exception here would
        surface as a mysterious background error on a turn the user already
        considers finished.
        """
        try:
            candidates = await self._candidates(
                user_message=user_message, assistant_message=assistant_message
            )
            if not candidates:
                return WriteResult()

            disabled = await memory_service.disabled_categories(session, user_id)
            result = WriteResult()
            for candidate in candidates:
                if candidate.category in disabled:
                    # A disabled category is not stored at all, not merely hidden:
                    # the user said not to keep this kind of thing (docs/12).
                    continue
                result = await self._store(
                    session,
                    user_id,
                    candidate,
                    result,
                    source_message_id=source_message_id,
                    project_id=project_id,
                )
            await session.commit()
            log.info(
                "memory.write_exchange",
                inserted=result.inserted,
                merged=result.merged,
                duplicates=result.duplicates,
            )
            return result
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("memory.write_failed", error=str(exc))
            await session.rollback()
            return WriteResult()

    async def _candidates(
        self, *, user_message: str, assistant_message: str
    ) -> list[MemoryCandidate]:
        forced = forced_candidate(user_message)
        if forced is not None:
            # An explicit instruction is the whole intent of the turn; extracting
            # additional guesses alongside it would bury what was asked for.
            return [forced]
        if not self._settings.memory_extraction_enabled:
            return []
        return await self._extractor.extract(
            user_message=user_message, assistant_message=assistant_message
        )

    async def _store(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        candidate: MemoryCandidate,
        result: WriteResult,
        *,
        source_message_id: uuid.UUID | None,
        project_id: uuid.UUID | None,
    ) -> WriteResult:
        embedding = (await self._embedder.embed([candidate.content]))[0]
        nearest = await memory_service.nearest_in_category(
            session, user_id, embedding, candidate.category
        )

        if nearest is not None and nearest[1] >= DUPLICATE_THRESHOLD:
            await memory_service.refresh_duplicate(session, nearest[0].id)
            return WriteResult(
                inserted=result.inserted,
                merged=result.merged,
                duplicates=result.duplicates + 1,
                memory_ids=result.memory_ids,
            )

        if nearest is not None and nearest[1] >= MERGE_THRESHOLD:
            old = nearest[0]
            merged_content = merge_content(old.content, candidate.content)
            merged_embedding = (await self._embedder.embed([merged_content]))[0]
            created = await memory_service.create(
                session,
                user_id,
                content=merged_content,
                category=candidate.category,
                # The merged memory inherits the higher importance: an update to
                # something important is still important.
                importance=max(old.importance, candidate.importance),
                why=candidate.why or old.why,
                embedding=merged_embedding,
                source=candidate.source,
                source_message_id=source_message_id,
                project_id=project_id or old.project_id,
            )
            await memory_service.supersede(session, old.id, created.id)
            return WriteResult(
                inserted=result.inserted,
                merged=result.merged + 1,
                duplicates=result.duplicates,
                memory_ids=(*result.memory_ids, created.id),
            )

        created = await memory_service.create(
            session,
            user_id,
            content=candidate.content,
            category=candidate.category,
            importance=candidate.importance,
            why=candidate.why,
            embedding=embedding,
            source=candidate.source,
            source_message_id=source_message_id,
            project_id=project_id if candidate.category is MemoryCategory.PROJECT else None,
        )
        return WriteResult(
            inserted=result.inserted + 1,
            merged=result.merged,
            duplicates=result.duplicates,
            memory_ids=(*result.memory_ids, created.id),
        )


def merge_content(old: str, new: str) -> str:
    """Combine an existing memory with its update.

    Deliberately mechanical rather than a second model call: the merge happens on a
    background path where a failed or slow call would silently lose the update, and
    the newer statement is what should lead. The older text is kept as context
    because it often carries a detail the update omits.
    """
    old, new = old.strip(), new.strip()
    if old.lower() in new.lower():
        return new
    return f"{new} (previously: {old})"
