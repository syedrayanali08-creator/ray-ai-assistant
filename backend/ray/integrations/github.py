"""GitHub read-only adapter.

Uses the GitHub REST API through ``httpx``. No SDK is installed because the API
surface we need is small: repo metadata, tree, file contents, issues, and commits.
"""

from __future__ import annotations

import base64
import os
from typing import Any
from urllib.parse import quote

import httpx

from ray.integrations.base import Adapter, AdapterResult

_GITHUB_API = "https://api.github.com"


class GitHubAdapter(Adapter):
    """Read-only GitHub access for the Coding and Research agents."""

    name = "github"

    def __init__(self, token: str | None = None) -> None:
        # Fall back to the conventional environment variable if no token is passed.
        self.token = token or os.environ.get("RAY_GITHUB_TOKEN")

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def check(self) -> AdapterResult:
        if not self.token:
            return AdapterResult(ok=False, data={}, error="No GitHub token configured.")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(f"{_GITHUB_API}/user", headers=self._headers())
            if response.status_code == 200:
                return AdapterResult(ok=True, data={"user": response.json().get("login")})
            if response.status_code == 401:
                return AdapterResult(ok=False, data={}, error="Invalid GitHub token.")
            return AdapterResult(
                ok=False, data={}, error=f"GitHub returned {response.status_code}."
            )
        except httpx.HTTPError as exc:
            return AdapterResult(ok=False, data={}, error=f"Could not reach GitHub: {exc}")

    async def read(self, path: str, **kwargs: Any) -> AdapterResult:
        """Dispatch to the right GitHub API based on ``resource``."""
        resource = kwargs.get("resource", "repo")
        if resource == "repo":
            return await self.get_repo(path)
        if resource == "tree":
            return await self.get_tree(path, ref=kwargs.get("ref", "HEAD"))
        if resource == "file":
            file_path = kwargs.get("path")
            if not file_path:
                return AdapterResult(ok=False, data={}, error="path is required for file.")
            return await self.get_file(path, path=str(file_path), ref=kwargs.get("ref", "HEAD"))
        if resource == "issues":
            return await self.get_issues(path, state=kwargs.get("state", "open"))
        if resource == "commits":
            return await self.get_commits(path, limit=kwargs.get("limit", 10))
        return AdapterResult(ok=False, data={}, error=f"Unknown GitHub resource {resource!r}.")

    def _repo_tuple(self, repo: str) -> tuple[str, str]:
        parts = repo.split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError("repo must be 'owner/name'.")
        return parts[0], parts[1]

    async def _get(self, url: str) -> AdapterResult:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=self._headers())
            body = response.json()
            if response.status_code == 200:
                return AdapterResult(
                    ok=True, data=body if isinstance(body, dict) else {"items": body}
                )
            message = (
                body.get("message", f"HTTP {response.status_code}")
                if isinstance(body, dict)
                else f"HTTP {response.status_code}"
            )
            return AdapterResult(ok=False, data={}, error=message)
        except httpx.HTTPError as exc:
            return AdapterResult(ok=False, data={}, error=f"GitHub request failed: {exc}")

    async def get_repo(self, repo: str) -> AdapterResult:
        owner, name = self._repo_tuple(repo)
        return await self._get(f"{_GITHUB_API}/repos/{owner}/{name}")

    async def get_tree(self, repo: str, *, ref: str = "HEAD") -> AdapterResult:
        owner, name = self._repo_tuple(repo)
        # Get the commit/tree recursively, limited to a reasonable depth.
        url = f"{_GITHUB_API}/repos/{owner}/{name}/git/trees/{quote(ref, safe='')}?recursive=1"
        result = await self._get(url)
        if not result.ok:
            return result
        tree = result.data.get("tree", [])
        files = [
            {"path": item["path"], "type": item["type"], "size": item.get("size")}
            for item in tree
            if isinstance(item, dict)
        ]
        return AdapterResult(
            ok=True, data={"files": files, "truncated": result.data.get("truncated", False)}
        )

    async def get_file(self, repo: str, *, path: str, ref: str = "HEAD") -> AdapterResult:
        owner, name = self._repo_tuple(repo)
        encoded_path = quote(path, safe="/")
        url = (
            f"{_GITHUB_API}/repos/{owner}/{name}/contents/{encoded_path}?ref={quote(ref, safe='')}"
        )
        result = await self._get(url)
        if not result.ok:
            return result
        content = result.data.get("content", "")
        try:
            decoded = base64.b64decode(content.replace("\n", "")).decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            decoded = ""
        return AdapterResult(
            ok=True,
            data={
                "path": result.data.get("path", path),
                "sha": result.data.get("sha"),
                "size": result.data.get("size"),
                "content": decoded,
            },
        )

    async def get_issues(self, repo: str, *, state: str = "open") -> AdapterResult:
        owner, name = self._repo_tuple(repo)
        url = f"{_GITHUB_API}/repos/{owner}/{name}/issues?state={state}&per_page=20"
        result = await self._get(url)
        if not result.ok:
            return result
        items = result.data if isinstance(result.data, list) else result.data.get("items", [])
        issues = [
            {
                "number": item.get("number"),
                "title": item.get("title"),
                "state": item.get("state"),
                "labels": [
                    label.get("name") for label in item.get("labels", []) if isinstance(label, dict)
                ],
                "body": item.get("body", "")[:500],
            }
            for item in items
            if isinstance(item, dict)
        ]
        return AdapterResult(ok=True, data={"issues": issues})

    async def get_commits(self, repo: str, *, limit: int = 10) -> AdapterResult:
        owner, name = self._repo_tuple(repo)
        url = f"{_GITHUB_API}/repos/{owner}/{name}/commits?per_page={limit}"
        result = await self._get(url)
        if not result.ok:
            return result
        items = result.data if isinstance(result.data, list) else result.data.get("items", [])
        commits = [
            {
                "sha": item.get("sha", "")[:7],
                "message": item.get("commit", {}).get("message", "").split("\n")[0],
                "author": item.get("commit", {}).get("author", {}).get("name"),
                "date": item.get("commit", {}).get("author", {}).get("date"),
            }
            for item in items
            if isinstance(item, dict)
        ]
        return AdapterResult(ok=True, data={"commits": commits})
