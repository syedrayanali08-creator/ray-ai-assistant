"""Deciding what is worth remembering (ADR-0013).

Two paths, because they have different authority:

* The user says "Ray, remember that…" — an instruction. Stored, no judgement applied.
* Ray reads the exchange and proposes candidates — a guess. Filtered hard, because
  the failure mode of a memory system is not forgetting, it is accumulating
  plausible noise until retrieval stops working.

Extraction is a *cheap* model call on the ``router`` role and runs after the answer
is streamed, so it never sits in the user's latency path.
"""

import json
import re
from dataclasses import dataclass

import structlog

from ray.domain.enums import MemoryCategory, MemorySource
from ray.llm.base import CompletionRequest, LLMError, LLMMessage
from ray.llm.registry import ProviderRegistry

log = structlog.get_logger()

# "Ray, remember that I prefer X" / "remember: X" / "please remember I use Y".
FORCED_WRITE = re.compile(
    r"^\s*(?:ray[,\s]+)?(?:please\s+)?remember\s*(?:that\s+|this[:,]\s*|:\s*)?(?P<content>.+)$",
    re.IGNORECASE | re.DOTALL,
)

MIN_IMPORTANCE = 2
"""Below this, a candidate is not worth the retrieval noise it adds."""

FORCED_IMPORTANCE = 4
"""An explicit instruction outranks anything Ray inferred on its own."""

EXTRACTION_PROMPT = """You extract durable facts about a user from one exchange.

Return ONLY a JSON array. Each element:
{"category": "user|project|learning|goal|conversation",
 "content": "...", "importance": 1-5, "why": "..."}

A fact qualifies only if BOTH are true:
- durable: still true next week, not about this specific request
- actionable: it would change how you answer a future question

Never extract: the question that was just asked, one-off factual lookups, anything
you inferred rather than were told, or anything sensitive the user did not choose to
share. Prefer zero memories over a weak one. Write each fact in the third person,
naming the user's own words where possible.

Return [] when nothing qualifies."""


@dataclass(frozen=True)
class MemoryCandidate:
    content: str
    category: MemoryCategory
    importance: int
    why: str
    source: MemorySource = MemorySource.CONVERSATION


def forced_candidate(message: str) -> MemoryCandidate | None:
    """A direct instruction to remember, if that is what this message is.

    Matched with a regex rather than a model call: the user asked plainly, and
    spending a model call — with a chance of it deciding not to comply — on an
    explicit instruction would be both slower and less obedient.
    """
    match = FORCED_WRITE.match(message.strip())
    if match is None:
        return None
    content = match.group("content").strip().rstrip(".")
    if not content:
        return None
    return MemoryCandidate(
        content=content,
        category=MemoryCategory.USER,
        importance=FORCED_IMPORTANCE,
        why="The user asked Ray to remember this.",
        source=MemorySource.USER,
    )


class MemoryExtractor:
    """Asks a cheap model what, if anything, this exchange taught Ray."""

    def __init__(self, providers: ProviderRegistry) -> None:
        self._providers = providers

    async def extract(self, *, user_message: str, assistant_message: str) -> list[MemoryCandidate]:
        request = CompletionRequest(
            messages=[
                LLMMessage(
                    role="user",
                    content=f"User said:\n{user_message}\n\nRay answered:\n{assistant_message}",
                )
            ],
            system=EXTRACTION_PROMPT,
            # Extraction is a classification, not a composition: near-zero
            # temperature keeps the same exchange producing the same memories.
            temperature=0.0,
        )
        try:
            completion = await self._providers.complete(request, role="router")
        except LLMError as exc:
            # Failing to learn from an exchange is not failing the exchange.
            log.info("memory.extraction_unavailable", error=str(exc))
            return []

        return [
            candidate
            for candidate in parse_candidates(completion.text)
            if candidate.importance >= MIN_IMPORTANCE
        ]


def parse_candidates(text: str) -> list[MemoryCandidate]:
    """Parse the model's JSON, tolerating the ways models wrap it.

    Anything unparseable yields nothing: a malformed extraction must not become a
    malformed memory, and it must never raise into the turn that produced it.
    """
    payload = _json_array(text)
    if payload is None:
        return []

    candidates: list[MemoryCandidate] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "")).strip()
        raw_category = str(item.get("category", "")).strip().lower()
        if not content or raw_category not in set(MemoryCategory):
            continue
        try:
            importance = int(item.get("importance", 3))
        except (TypeError, ValueError):
            importance = 3
        candidates.append(
            MemoryCandidate(
                content=content[:4_000],
                category=MemoryCategory(raw_category),
                importance=max(1, min(5, importance)),
                why=str(item.get("why", "")).strip()[:500],
            )
        )
    return candidates


def _json_array(text: str) -> list[object] | None:
    stripped = text.strip()
    # Fenced output is common enough to handle rather than reject.
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?|```$", "", stripped).strip()
    start, end = stripped.find("["), stripped.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None
