"""The ranking policy (ADR-0013), and the fact that SQL agrees with it."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ray.db.models import Memory
from ray.domain.enums import MemoryCategory
from ray.memory.embeddings import HashingEmbedder
from ray.memory.scoring import (
    DEFAULT_WEIGHTS,
    hybrid_score,
    importance_component,
    recency_component,
    usage_component,
    within_budget,
)
from ray.services import memory_service


def test_importance_is_normalised_across_the_whole_scale() -> None:
    assert importance_component(1) == 0.0
    assert importance_component(5) == 1.0
    assert importance_component(3) == 0.5
    # Out-of-range values are clamped rather than distorting the score.
    assert importance_component(9) == 1.0


def test_recency_halves_every_thirty_days() -> None:
    assert recency_component(0) == 1.0
    assert recency_component(30) == pytest.approx(0.5)
    assert recency_component(60) == pytest.approx(0.25)


def test_usage_saturates_so_one_favourite_cannot_dominate() -> None:
    assert usage_component(0) == 0.0
    assert usage_component(10) == 1.0
    assert usage_component(500) == 1.0


def test_importance_breaks_a_similarity_tie() -> None:
    """The reason retrieval is not pure vector search."""
    trivial = hybrid_score(similarity=0.80, importance=1, age_days=0, hit_count=0)
    important = hybrid_score(similarity=0.75, importance=5, age_days=0, hit_count=0)
    assert important > trivial


def test_the_active_project_boosts_its_own_memories() -> None:
    generic = hybrid_score(similarity=0.7, importance=3, age_days=0, hit_count=0)
    scoped = hybrid_score(similarity=0.7, importance=3, age_days=0, hit_count=0, same_project=True)
    assert scoped - generic == pytest.approx(DEFAULT_WEIGHTS.project_boost)


def test_budget_drops_whole_memories_never_half_of_one() -> None:
    kept = within_budget(["a" * 40, "b" * 40, "c" * 40], char_budget=90)
    assert kept == ["a" * 40, "b" * 40]


async def test_sql_score_matches_the_python_formula(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    """The formula exists in two places; this is what keeps them honest."""
    embedder = HashingEmbedder()
    content = "The user is building a Processing game called Starfall Sprint"
    embedding = (await embedder.embed([content]))[0]
    session.add(
        Memory(
            user_id=user_id,
            category=MemoryCategory.PROJECT,
            content=content,
            importance=4,
            embedding=embedding,
            hit_count=3,
        )
    )
    await session.commit()

    query_vector = (await embedder.embed(["What am I building in Processing?"]))[0]
    found = await memory_service.search(session, user_id, query_vector, limit=5)
    assert len(found) == 1
    memory, similarity, score = found[0]

    expected = hybrid_score(
        similarity=similarity,
        importance=memory.importance,
        # Just written, so the recency term is ~1; a tolerance covers the seconds
        # between the insert and the query.
        age_days=0.0,
        hit_count=memory.hit_count,
    )
    assert score == pytest.approx(expected, abs=0.01)
