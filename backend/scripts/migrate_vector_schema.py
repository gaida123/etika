"""Prepare ``knowledge_chunks`` for Gemini/TiDB semantic retrieval.

Run from ``backend/``. The default is a read-only plan:

    python scripts/migrate_vector_schema.py
    python scripts/migrate_vector_schema.py --apply

After the backfill succeeds, create the vector index. Request the required TiFlash
replica separately, wait for it to become ready, then create the index:

    python scripts/migrate_vector_schema.py --apply --enable-tiflash
    python scripts/migrate_vector_schema.py --apply --create-index

The script never drops or rewrites existing source/chunk data.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import get_engine  # noqa: E402
from app.core.settings import get_settings  # noqa: E402


TABLE = "knowledge_chunks"
VECTOR_INDEX = "idx_knowledge_chunks_embedding"


def _columns() -> set[str]:
    statement = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = :table_name
        """
    )
    with get_engine().connect() as connection:
        return {str(row[0]) for row in connection.execute(statement, {"table_name": TABLE})}


def _index_exists() -> bool:
    with get_engine().connect() as connection:
        rows = connection.execute(text(f"SHOW INDEX FROM {TABLE}")).mappings()
        return any(str(row.get("Key_name", "")).casefold() == VECTOR_INDEX for row in rows)


def _execute(sql: str) -> None:
    with get_engine().begin() as connection:
        connection.execute(text(sql))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="execute the planned non-destructive DDL")
    parser.add_argument(
        "--enable-tiflash",
        action="store_true",
        help="request one TiFlash replica; required before an HNSW vector index",
    )
    parser.add_argument(
        "--create-index",
        action="store_true",
        help="create the HNSW vector index after the column/backfill are ready",
    )
    args = parser.parse_args()
    settings = get_settings()
    dimensions = settings.gemini_embedding_dimensions
    if dimensions <= 0:
        raise ValueError("GEMINI_EMBEDDING_DIMENSIONS must be positive")
    if (args.enable_tiflash or args.create_index) and not args.apply:
        parser.error("--enable-tiflash and --create-index require --apply")
    if args.enable_tiflash and args.create_index:
        parser.error("request TiFlash first; wait for readiness before --create-index")

    columns = _columns()
    if not columns:
        raise RuntimeError("knowledge_chunks was not found in the configured database")

    planned: list[str] = []
    if "embedding" not in columns:
        planned.append(f"ALTER TABLE {TABLE} ADD COLUMN embedding VECTOR({dimensions}) NULL")
    if "embedding_model" not in columns:
        planned.append(f"ALTER TABLE {TABLE} ADD COLUMN embedding_model VARCHAR(128) NULL")
    if "embedded_at" not in columns:
        planned.append(f"ALTER TABLE {TABLE} ADD COLUMN embedded_at DATETIME NULL")
    if "embedded_text_hash" not in columns:
        planned.append(f"ALTER TABLE {TABLE} ADD COLUMN embedded_text_hash CHAR(64) NULL")
    if args.enable_tiflash:
        planned.append(f"ALTER TABLE {TABLE} SET TIFLASH REPLICA 1")
    if args.create_index and not _index_exists():
        planned.append(
            f"CREATE VECTOR INDEX {VECTOR_INDEX} "
            f"ON {TABLE} ((VEC_COSINE_DISTANCE(embedding))) USING HNSW"
        )

    if not planned:
        print("Vector schema is already ready; no DDL needed.")
        return
    action = "Applying" if args.apply else "Planned (dry run)"
    for sql in planned:
        print(f"{action}: {sql}")
        if args.apply:
            _execute(sql)
    if args.apply and args.enable_tiflash:
        print("TiFlash replica requested. Wait for it to become ready before creating the HNSW index.")
    elif args.apply and not args.create_index:
        print("Schema applied. Next: run backfill_embeddings.py, then create the HNSW index.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Some database error strings can include connection details. Keep CLI output safe.
        print(f"FAILED: {type(exc).__name__}. Vector schema migration did not complete.", file=sys.stderr)
        sys.exit(1)
