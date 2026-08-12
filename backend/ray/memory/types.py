"""Memory shapes with no dependencies.

Separate from ``retrieval`` because an agent is handed retrieved memories but must
not be able to reach the database: the retriever imports the service layer, so a
shared *type* living next to it would drag the whole persistence layer into
``ray.agents`` and break the import-linter contract from ADR-0005.
"""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedMemory:
    id: uuid.UUID
    content: str
    category: str
    # Hybrid score from ADR-0013, surfaced so the HUD can show why a memory won.
    score: float
    similarity: float = 0.0
    importance: int = 3
