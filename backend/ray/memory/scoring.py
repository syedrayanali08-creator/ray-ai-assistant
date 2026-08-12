"""Retrieval scoring and the thresholds that keep the store from rotting (ADR-0013).

Pure functions and constants, deliberately separate from both the SQL that applies
them and the model that fills the store: the ranking policy is the part most likely
to be tuned, and tuning it should not mean editing a query.

The same formula exists twice — here in Python and in SQL (``memory_service``) —
because ranking has to happen in the database (it filters and orders before the rows
come back) while the *policy* has to be readable and testable without one. The tests
assert the two agree.
"""

from dataclasses import dataclass

# Cosine similarity thresholds for the write path.
DUPLICATE_THRESHOLD = 0.95
"""At or above this, a candidate says nothing new: refresh the existing row instead."""

MERGE_THRESHOLD = 0.85
"""Between merge and duplicate, a candidate is an *update* to what Ray already knows."""

RECENCY_HALF_LIFE_DAYS = 30.0
"""A memory untouched for a month counts half as recent. Not a deletion policy."""

USAGE_SATURATION = 10
"""Hits beyond this stop adding score, so a single favourite cannot dominate."""


@dataclass(frozen=True)
class MemoryWeights:
    """How the four signals combine. Configuration, not a constant of nature."""

    similarity: float = 0.55
    importance: float = 0.20
    recency: float = 0.15
    usage: float = 0.10
    project_boost: float = 0.05
    """Added when a memory belongs to the project the request is about."""


DEFAULT_WEIGHTS = MemoryWeights()


def importance_component(importance: int) -> float:
    """1-5 normalised to 0-1."""
    return (max(1, min(5, importance)) - 1) / 4


def recency_component(age_days: float) -> float:
    return float(0.5 ** (max(age_days, 0.0) / RECENCY_HALF_LIFE_DAYS))


def usage_component(hit_count: int) -> float:
    return min(max(hit_count, 0), USAGE_SATURATION) / USAGE_SATURATION


def hybrid_score(
    *,
    similarity: float,
    importance: int,
    age_days: float,
    hit_count: int,
    same_project: bool = False,
    weights: MemoryWeights = DEFAULT_WEIGHTS,
) -> float:
    """The ADR-0013 formula.

    Pure similarity is not enough: a stale, unimportant memory can be textually
    closer to the question than the important one that should have won.
    """
    score = (
        weights.similarity * similarity
        + weights.importance * importance_component(importance)
        + weights.recency * recency_component(age_days)
        + weights.usage * usage_component(hit_count)
    )
    if same_project:
        score += weights.project_boost
    return score


def within_budget(contents: list[str], *, char_budget: int) -> list[str]:
    """Take memories in score order until the context budget is spent.

    Truncation is by whole memories: half a memory is worse than none, because the
    model reads the fragment as a complete fact.
    """
    kept: list[str] = []
    spent = 0
    for content in contents:
        cost = len(content) + 3  # "- " and a newline, roughly
        if spent + cost > char_budget:
            continue
        kept.append(content)
        spent += cost
    return kept
