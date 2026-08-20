"""Local file-system adapter with allow-list enforcement.

Ray can read files inside directories the user explicitly allows. Paths outside the
allow-list are rejected before any filesystem access happens (ADR-0010).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from ray.integrations.base import Adapter, AdapterResult


class LocalFileAdapter(Adapter):
    """Read-only access to allowed directories."""

    name = "files"

    def __init__(self, allowed_paths: list[str] | None = None) -> None:
        self.allowed_paths = allowed_paths or []

    def _resolve(self, path: str) -> Path | None:
        raw = Path(path).expanduser()
        if raw.is_absolute():
            candidate = raw.resolve()
            for allowed in self.allowed_paths:
                allowed_path = Path(allowed).expanduser().resolve()
                try:
                    candidate.relative_to(allowed_path)
                    return candidate
                except ValueError:
                    continue
            return None

        # Relative paths are resolved against each allowed root.
        for allowed in self.allowed_paths:
            allowed_path = Path(allowed).expanduser().resolve()
            candidate = (allowed_path / raw).resolve()
            try:
                candidate.relative_to(allowed_path)
                return candidate
            except ValueError:
                continue
        return None

    async def check(self) -> AdapterResult:
        def _check() -> tuple[list[str], str]:
            valid = [
                os.path.realpath(p)
                for p in self.allowed_paths
                if os.path.isdir(os.path.expanduser(p))
            ]
            return valid, "" if valid else "No allowed directories are configured or reachable."

        valid, error = await asyncio.to_thread(_check)
        return AdapterResult(ok=len(valid) > 0, data={"allowed": valid}, error=error)

    async def read(self, path: str = "", **kwargs: Any) -> AdapterResult:
        return await asyncio.to_thread(self._read_sync, path)

    def _read_sync(self, path: str) -> AdapterResult:
        target = self._resolve(path)
        if target is None:
            return AdapterResult(ok=False, data={}, error=f"{path!r} is outside the allow-list.")
        if not target.exists():
            return AdapterResult(ok=False, data={}, error=f"{path!r} does not exist.")
        if target.is_dir():
            try:
                children = [
                    {"name": child.name, "type": "directory" if child.is_dir() else "file"}
                    for child in target.iterdir()
                ]
            except OSError as exc:
                return AdapterResult(ok=False, data={}, error=f"Could not list directory: {exc}")
            return AdapterResult(
                ok=True, data={"path": path, "type": "directory", "children": children}
            )
        if target.is_file():
            # Refuse binary files by checking for null bytes in a sample.
            try:
                with target.open("rb") as f:
                    sample = f.read(4096)
            except OSError as exc:
                return AdapterResult(ok=False, data={}, error=f"Could not read file: {exc}")
            if b"\x00" in sample:
                return AdapterResult(ok=False, data={}, error="Binary files are not read.")
            text = (
                sample.decode("utf-8", errors="replace")
                + target.read_text(encoding="utf-8", errors="replace")[len(sample) :]
            )
            return AdapterResult(
                ok=True,
                data={
                    "path": path,
                    "type": "file",
                    "size": target.stat().st_size,
                    "content": text,
                },
            )
        return AdapterResult(ok=False, data={}, error=f"{path!r} is not a file or directory.")
