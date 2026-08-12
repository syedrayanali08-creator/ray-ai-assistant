"""The embedding backends (ADR-0003, ADR-0016)."""

import math

import pytest

from ray.config import get_settings
from ray.memory.embeddings import HashingEmbedder, get_embedder


async def test_vectors_match_the_column_width() -> None:
    """A mismatch here is an insert failure, not a quality problem."""
    embedder = HashingEmbedder()
    vectors = await embedder.embed(["hello", "world"])
    assert embedder.dimension == get_settings().embedding_dim
    assert [len(vector) for vector in vectors] == [embedder.dimension] * 2


async def test_vectors_are_normalised_so_cosine_similarity_is_comparable() -> None:
    vector = (await HashingEmbedder().embed(["The user is learning calculus"]))[0]
    assert math.sqrt(sum(value * value for value in vector)) == pytest.approx(1.0)


async def test_the_same_text_always_gives_the_same_vector() -> None:
    """Determinism is what makes the dedupe thresholds testable."""
    embedder = HashingEmbedder()
    first = await embedder.embed(["Starfall Sprint"])
    second = await embedder.embed(["Starfall Sprint"])
    assert first == second


async def test_similar_text_scores_far_above_unrelated_text() -> None:
    """The hashing backend is a real embedder, not a stub: the dedupe thresholds in
    ADR-0013 are only meaningful if similarity separates these cases."""
    embedder = HashingEmbedder()
    game, restated, unrelated = await embedder.embed(
        [
            "The user is building a Processing game called Starfall Sprint",
            "Starfall Sprint is a Processing game the user is building",
            "The user dislikes pineapple on pizza",
        ]
    )

    def cosine(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert cosine(game, restated) > 0.85
    assert cosine(game, unrelated) < 0.2


async def test_an_empty_string_does_not_produce_a_broken_vector() -> None:
    vector = (await HashingEmbedder().embed([""]))[0]
    assert len(vector) == get_settings().embedding_dim
    assert set(vector) == {0.0}


def test_the_configured_backend_is_honoured() -> None:
    hashing = get_settings().model_copy(update={"embedding_backend": "hashing"})
    assert isinstance(get_embedder_with(hashing), HashingEmbedder)


def get_embedder_with(settings: object) -> object:
    """`get_embedder` reads the cached settings, so the override is applied there."""
    from unittest.mock import patch

    with patch("ray.memory.embeddings.get_settings", return_value=settings):
        return get_embedder()


def test_a_missing_model_install_degrades_instead_of_raising() -> None:
    """Requesting the model backend on a machine without torch must not break Ray
    (ADR-0015's principle, applied to embeddings)."""
    import builtins
    from unittest.mock import patch

    settings = get_settings().model_copy(update={"embedding_backend": "sentence-transformers"})
    real_import = builtins.__import__

    def fail_on_sentence_transformers(name: str, *args: object, **kwargs: object) -> object:
        if name == "sentence_transformers":
            raise ImportError("No module named 'sentence_transformers'")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    with (
        patch("ray.memory.embeddings.get_settings", return_value=settings),
        patch.object(builtins, "__import__", fail_on_sentence_transformers),
    ):
        assert isinstance(get_embedder(), HashingEmbedder)
