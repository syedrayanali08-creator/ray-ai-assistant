"""Knowledge adapter for local Obsidian vaults (and future Notion support).

An Obsidian vault is just a directory of Markdown files. This adapter walks the
configured path and reads notes without requiring an API or network call, which
fits the local-first requirement (ADR-0010).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ray.integrations.base import Adapter, AdapterResult


class ObsidianAdapter(Adapter):
    """Read and search an Obsidian vault directory."""

    name = "obsidian"

    def __init__(self, vault_path: str | None = None) -> None:
        self.vault_path = vault_path

    def _vault(self) -> Path | None:
        if not self.vault_path:
            return None
        path = Path(self.vault_path).expanduser().resolve()
        if not path.is_dir():
            return None
        return path

    async def check(self) -> AdapterResult:
        path = self._vault()
        if not path:
            return AdapterResult(
                ok=False, data={}, error="Obsidian vault path is not configured or does not exist."
            )
        md_files = list(path.rglob("*.md"))
        return AdapterResult(ok=True, data={"vault": str(path), "note_count": len(md_files)})

    async def read(self, path: str = "", **kwargs: Any) -> AdapterResult:
        """Read a note by relative path, or search all notes if ``query`` is given."""
        query = kwargs.get("query")
        if query is not None:
            return await self.search(str(query))
        return await self.get_note(path)

    async def get_note(self, relative_path: str) -> AdapterResult:
        vault = self._vault()
        if not vault:
            return AdapterResult(ok=False, data={}, error="No vault configured.")
        note_path = (vault / relative_path).resolve()
        # Guard against traversal outside the vault.
        if not str(note_path).startswith(str(vault)):
            return AdapterResult(ok=False, data={}, error="Path is outside the vault.")
        if not note_path.is_file():
            return AdapterResult(ok=False, data={}, error=f"Note {relative_path!r} not found.")
        try:
            content = note_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return AdapterResult(ok=False, data={}, error=f"Could not read note: {exc}")
        return AdapterResult(
            ok=True,
            data={
                "path": relative_path,
                "name": note_path.stem,
                "content": content,
                "word_count": len(content.split()),
            },
        )

    async def search(self, query: str, *, limit: int = 10) -> AdapterResult:
        vault = self._vault()
        if not vault:
            return AdapterResult(ok=False, data={}, error="No vault configured.")
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        matches: list[dict[str, Any]] = []
        for md_file in vault.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if pattern.search(content):
                rel = str(md_file.relative_to(vault))
                # Find the first matching line as a preview.
                preview = ""
                for line in content.splitlines():
                    if pattern.search(line):
                        preview = line.strip()
                        break
                matches.append({"path": rel, "name": md_file.stem, "preview": preview})
                if len(matches) >= limit:
                    break
        return AdapterResult(
            ok=True, data={"query": query, "matches": matches, "count": len(matches)}
        )


class NotionAdapter(Adapter):
    """Placeholder for a future Notion-backed knowledge provider."""

    name = "notion"

    def __init__(self, token: str | None = None) -> None:
        self.token = token

    async def check(self) -> AdapterResult:
        return AdapterResult(
            ok=False, data={}, error="Notion integration is not implemented in V1."
        )

    async def read(self, path: str = "", **kwargs: Any) -> AdapterResult:
        return await self.check()
