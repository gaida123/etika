"""Load the reviewed demo registry into the configured database.

Run from ``backend/``:
    python scripts/load_registry.py --apply

The loader inserts/updates only IDs present in the JSON file. It never deletes
other requirements. Placeholder action URLs are stored as NULL, never exposed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import get_sessionmaker, init_db  # noqa: E402
from app.core.settings import BACKEND_DIR  # noqa: E402
from app.knowledge.tidb_registry import load_registry_file, upsert_requirements  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the parsed rows")
    parser.add_argument(
        "--path", default=str(BACKEND_DIR / "data" / "registry" / "requirements.json"), help="registry JSON path"
    )
    args = parser.parse_args()
    requirements = load_registry_file(args.path)
    print(f"Validated {len(requirements)} registry requirement(s).")
    if not args.apply:
        print("Dry run only; no database writes were made.")
        return
    init_db()
    with get_sessionmaker()() as session:
        count = upsert_requirements(session, requirements)
        session.commit()
    print(f"Loaded {count} requirement(s). Placeholder action URLs were stored as unavailable.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}. Registry load did not complete.", file=sys.stderr)
        sys.exit(1)
