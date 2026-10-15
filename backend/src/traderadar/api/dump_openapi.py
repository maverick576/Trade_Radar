"""CLI utility to dump OpenAPI schema JSON to frontend directory."""

import json
from pathlib import Path

from traderadar.api.app import app


def dump() -> None:
    """Generate and write openapi.json."""
    schema = app.openapi()
    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        frontend_dir = Path("../frontend")

    target = frontend_dir / "openapi.json"
    with open(target, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    print(f"OpenAPI schema successfully written to {target.resolve()}")


if __name__ == "__main__":
    dump()
