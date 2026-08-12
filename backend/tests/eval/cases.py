"""The memory evaluation set (`docs/15`, category 2).

Behaviour, not implementation. A case describes a seeded world, one request, and what
must be true about the memories Ray used — never about the wording of the answer, so
the set survives a prompt change and still catches a retrieval regression.

Cases live as data rather than as test functions so the runner can print a scorecard
and so tuning the ADR-0013 weights is a matter of re-running them and comparing.
"""

from dataclasses import dataclass, field

from ray.domain.enums import MemoryCategory


@dataclass(frozen=True)
class SeedMemory:
    key: str
    content: str
    category: MemoryCategory = MemoryCategory.PROJECT
    importance: int = 3
    days_old: float = 0.0


@dataclass(frozen=True)
class MemoryCase:
    id: str
    """Stable: it is what a scorecard regression is reported against."""

    seed: tuple[SeedMemory, ...]
    query: str
    expect_keys: tuple[str, ...] = ()
    """Memory keys that must be retrieved, in no particular order."""
    reject_keys: tuple[str, ...] = ()
    """Memory keys that must NOT be retrieved."""
    expect_top: str | None = None
    """The key that must rank first, when the case is about ranking."""
    delete_keys: tuple[str, ...] = ()
    disabled_categories: tuple[MemoryCategory, ...] = ()
    notes: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


STARFALL = SeedMemory(
    key="project.starfall",
    content="The user is building a Processing game called Starfall Sprint with mouse aiming",
    category=MemoryCategory.PROJECT,
    importance=4,
)
WATERLOO = SeedMemory(
    key="goal.waterloo",
    content="The user is applying to Waterloo Computer Science",
    category=MemoryCategory.GOAL,
    importance=5,
)
PIZZA = SeedMemory(
    key="user.pizza",
    content="The user dislikes pineapple on pizza",
    category=MemoryCategory.USER,
    importance=2,
)
CALCULUS = SeedMemory(
    key="learning.calculus",
    content="The user is learning calculus and prefers worked examples over theory",
    category=MemoryCategory.LEARNING,
    importance=3,
)

CASES: tuple[MemoryCase, ...] = (
    MemoryCase(
        id="memory-recalls-active-project",
        seed=(STARFALL, PIZZA, CALCULUS),
        query="What am I working on?",
        expect_keys=("project.starfall",),
        reject_keys=("user.pizza",),
        notes="Phase 3 completion criterion: a brand-new conversation still knows.",
        tags=("completion",),
    ),
    MemoryCase(
        id="memory-recalls-without-being-named",
        seed=(STARFALL, CALCULUS),
        query="What should I implement next in my game?",
        expect_keys=("project.starfall",),
        notes="Retrieval is semantic: the project is never named in the question.",
    ),
    MemoryCase(
        id="memory-deleted-is-not-retrieved",
        seed=(STARFALL,),
        query="What am I working on?",
        delete_keys=("project.starfall",),
        reject_keys=("project.starfall",),
        notes="Phase 3 completion criterion: delete means deleted, immediately.",
        tags=("completion",),
    ),
    MemoryCase(
        id="memory-disabled-category-is-not-retrieved",
        seed=(STARFALL,),
        query="What am I working on?",
        disabled_categories=(MemoryCategory.PROJECT,),
        reject_keys=("project.starfall",),
    ),
    MemoryCase(
        id="memory-unrelated-is-not-retrieved",
        seed=(PIZZA, CALCULUS),
        query="Which Processing game am I building?",
        reject_keys=("user.pizza", "learning.calculus"),
        notes="The min-score floor: a weak match costs context and misleads.",
    ),
    MemoryCase(
        id="memory-importance-wins-a-close-call",
        seed=(
            WATERLOO,
            SeedMemory(
                key="conversation.waterloo_chat",
                content="The user mentioned Waterloo in passing",
                category=MemoryCategory.CONVERSATION,
                importance=1,
            ),
        ),
        query="What are my Waterloo plans?",
        expect_top="goal.waterloo",
        notes=(
            "Why retrieval is hybrid rather than pure vector search: both memories "
            "mention Waterloo, and importance decides which one Ray uses."
        ),
    ),
    MemoryCase(
        id="memory-recency-breaks-a-tie",
        seed=(
            SeedMemory(
                key="project.old",
                content="The user is building a Processing game, player movement is done",
                days_old=400,
            ),
            SeedMemory(
                key="project.new",
                content="The user is building a Processing game, mouse aiming is done",
            ),
        ),
        query="How far along is my Processing game?",
        expect_top="project.new",
    ),
)
