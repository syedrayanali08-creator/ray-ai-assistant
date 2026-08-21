#!/usr/bin/env python3
"""Tag a Ray release and keep version files in sync.

Usage:
    uv run python backend/scripts/release.py 0.2.0
    uv run python backend/scripts/release.py 0.2.0 --message "Fixes voice latency"
"""

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "backend" / "pyproject.toml"
VERSION_FILE = ROOT / "backend" / "ray" / "version.py"
PACKAGE_JSON = ROOT / "frontend" / "package.json"
CHANGELOG = ROOT / "CHANGELOG.md"


def _replace(pattern: str, replacement: str, path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    new, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise ValueError(f"Could not update {path}")
    path.write_text(new, encoding="utf-8")


def set_version(version: str) -> None:
    _replace(r'^version = "[^"]+"', f'version = "{version}"', PYPROJECT)
    _replace(r'__version__ = "[^"]+"', f'__version__ = "{version}"', VERSION_FILE)

    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    package["version"] = version
    PACKAGE_JSON.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")


def update_changelog(version: str, message: str) -> None:
    heading = f"## [{version}] - {datetime.now(UTC).strftime('%Y-%m-%d')}"
    body = f"\n{message}\n"
    entry = f"{heading}\n{body}"
    if CHANGELOG.exists():
        existing = CHANGELOG.read_text(encoding="utf-8")
        if existing.startswith("# Changelog"):
            _, rest = existing.split("\n", 1)
            content = f"# Changelog\n\n{entry}{rest.lstrip()}"
        else:
            content = f"# Changelog\n\n{entry}{existing}"
    else:
        content = f"# Changelog\n\n{entry}"
    CHANGELOG.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tag a Ray release")
    parser.add_argument("version", help="Semantic version to tag, e.g. 0.2.0")
    parser.add_argument("--message", "-m", default="", help="Release notes for CHANGELOG.md")
    parser.add_argument("--no-commit", action="store_true", help="Skip git commit and tag")
    args = parser.parse_args()

    set_version(args.version)
    update_changelog(args.version, args.message or f"Release {args.version}")

    if not args.no_commit:
        subprocess.run(["git", "add", "-u"], cwd=ROOT, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"chore(release): {args.version}"],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(["git", "tag", f"v{args.version}"], cwd=ROOT, check=True)

    print(f"Ray {args.version} ready. Do not forget to push the tag: git push --tags")


if __name__ == "__main__":
    main()
