"""Local embeddings (ADR-0003).

Phase 3 does retrieval; Phase 2 fixes the interface and the dimension so that
turning retrieval on does not reshape the database or the pipeline.

The model is loaded lazily and only when something actually asks for a vector: it
is ~90 MB and several seconds of import, which would otherwise be paid by every
process, including the test suite.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ray.config import get_settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class TextEmbedder(ABC):
    """Turns text into a vector of exactly ``dimension`` floats."""

    @property
    @abstractmethod
    def dimension(self) -> int: ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder(TextEmbedder):
    """all-MiniLM-L6-v2 on the local machine: free, offline, 384 dimensions."""

    def __init__(self, model_name: str | None = None) -> None:
        settings = get_settings()
        self._model_name = model_name or settings.embedding_model
        self._dimension = settings.embedding_dim
        self._model: SentenceTransformer | None = None

    @property
    def dimension(self) -> int:
        return self._dimension

    def _load(self) -> "SentenceTransformer":
        if self._model is None:
            # Imported here rather than at module scope: sentence-transformers pulls
            # in torch, which is an optional install (`uv sync --group embeddings`)
            # and far too heavy to import for processes that never embed anything.
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        # Encoding is CPU-bound and blocking; a thread keeps the event loop free.
        vectors = await asyncio.to_thread(model.encode, texts)
        return [[float(value) for value in vector] for vector in vectors]
