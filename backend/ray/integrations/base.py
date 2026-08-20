"""Adapter interface for external integrations.

An adapter is a capability interface that may have several concrete providers. The
Tool Manager uses adapters through ``ray.tools.integration_tools``, never directly,
so credentials stay outside the agent context (ADR-0010).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class AdapterResult:
    """Normalised result from an adapter."""

    ok: bool
    data: dict[str, Any]
    error: str = ""


@runtime_checkable
class Adapter(Protocol):
    """Base protocol for all integration adapters."""

    name: str

    async def check(self) -> AdapterResult:
        """Health check without side effects."""
        ...

    async def read(self, path: str, **kwargs: Any) -> AdapterResult:
        """Read a resource from the integration."""
        ...
