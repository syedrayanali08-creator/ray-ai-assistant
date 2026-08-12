"""Local embeddings (ADR-0003).

The model is loaded lazily and only when something actually asks for a vector: it
is ~90 MB and several seconds of import, which would otherwise be paid by every
process, including the test suite.

Two backends exist for one reason: ``sentence-transformers`` pulls in torch, which
is an optional install, and Ray must still run — and CI must still be meaningful —
without it (ADR-0016). ``hashing`` produces real, stable, comparable vectors from
character n-grams; it is a worse *semantic* model, not a stub.
"""

import asyncio
import hashlib
import math
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import structlog

from ray.config import get_settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

log = structlog.get_logger()


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


class HashingEmbedder(TextEmbedder):
    """Hashed character n-grams, L2-normalised. No dependencies, no download.

    Words are hashed into the vector space, so texts sharing words land near each
    other and cosine similarity stays meaningful — enough for dedupe thresholds and
    for a deterministic test suite. It has no notion of synonyms, which is exactly
    what the sentence-transformer backend is for.
    """

    name = "hashing"

    def __init__(self, dimension: int | None = None) -> None:
        self._dimension = dimension or get_settings().embedding_dim

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        tokens = _tokenize(text)
        for token in tokens:
            # Trigrams as well as whole words, so "calculus" and "calculuses" are
            # near neighbours rather than unrelated.
            for feature in [token, *_trigrams(token)]:
                digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
                index = int.from_bytes(digest[:4], "big") % self._dimension
                # The sign bit spreads features in both directions, which keeps
                # unrelated texts near-orthogonal instead of all-positive.
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _trigrams(token: str) -> list[str]:
    if len(token) <= 3:
        return []
    return [token[i : i + 3] for i in range(len(token) - 2)]


def get_embedder() -> TextEmbedder:
    """The configured embedder, degrading rather than failing.

    A missing torch install is a setup state, not a crash: Ray logs which backend it
    ended up on and keeps working, the same way an unconfigured LLM provider falls
    through the chain (ADR-0015).
    """
    settings = get_settings()
    if settings.embedding_backend == "hashing":
        return HashingEmbedder()

    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        log.warning(
            "memory.embedder_unavailable",
            requested="sentence-transformers",
            using="hashing",
            hint="uv sync --group embeddings",
        )
        return HashingEmbedder()
    return SentenceTransformerEmbedder()
