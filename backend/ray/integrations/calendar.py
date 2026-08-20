"""Calendar adapter for local and future Google Calendar sync.

V1 keeps events in the local PostgreSQL calendar and supports ICS import/export. A
future ``GoogleCalendarAdapter`` would plug into the same ``CalendarAdapter`` seam.
"""

from __future__ import annotations

from typing import Any

from ray.integrations.base import Adapter, AdapterResult


class LocalCalendarAdapter(Adapter):
    """Local calendar: the database is the source of truth."""

    name = "local_calendar"

    async def check(self) -> AdapterResult:
        return AdapterResult(ok=True, data={}, error="")

    async def read(self, path: str = "", **kwargs: Any) -> AdapterResult:
        return AdapterResult(ok=True, data={"note": "Use calendar.list and calendar.create tools."})


class GoogleCalendarAdapter(Adapter):
    """Placeholder for optional Google Calendar OAuth sync."""

    name = "google_calendar"

    async def check(self) -> AdapterResult:
        return AdapterResult(
            ok=False,
            data={},
            error="Google Calendar sync is not implemented in V1. Use ICS import/export instead.",
        )

    async def read(self, path: str = "", **kwargs: Any) -> AdapterResult:
        return await self.check()
