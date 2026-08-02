"""Write the OpenAPI schema to disk.

The frontend generates its types from this file, so the API contract cannot drift
from the client without the generated types changing (ADR-0011).

Usage:
    uv run python scripts/export_openapi.py ../frontend/openapi.json
"""

import json
import sys
from pathlib import Path

from ray.main import create_app


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "../frontend/openapi.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(create_app().openapi(), indent=2) + "\n")
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
