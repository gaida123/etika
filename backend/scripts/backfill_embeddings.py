"""Backfill Gemini embeddings into the TiDB ``knowledge_chunks`` vector column.

This is deliberately resumable: only approved, current source content that has no
vector, used a different model, or changed since its last embedding is selected.
Run a dry plan first, then use --apply in modest batches:

    python scripts/backfill_embeddings.py
    python scripts/backfill_embeddings.py --apply --batch-size 5
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import bindparam, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import get_engine  # noqa: E402
from app.core.settings import get_settings  # noqa: E402
from app.knowledge.embeddings import EmbeddingUnavailable, GeminiEmbeddingService  # noqa: E402

APPROVED_REVIEW_STATUSES = (
    "approved",
    "approved_by_research_owner",
    "research_owner_approved",
)


def _pending_rows(limit: int | None) -> list[dict[str, object]]:
    statement_sql = """
        SELECT chunk_id, body_text, full_text, text_hash, normalised_content_hash,
               raw_content_hash, url
        FROM knowledge_chunks
        WHERE is_current = 1
          AND review_status IN :approved_statuses
          AND (embedding IS NULL OR embedding_model IS NULL OR embedding_model <> :model
               OR embedded_text_hash IS NULL
               OR embedded_text_hash <> COALESCE(text_hash, normalised_content_hash, raw_content_hash,
                                                 SHA2(full_text, 256)))
        ORDER BY chunk_id
    """
    if limit is not None:
        statement_sql += " LIMIT :limit"
    statement = text(statement_sql).bindparams(bindparam("approved_statuses", expanding=True))
    params: dict[str, object] = {
        "model": get_settings().gemini_embedding_model,
        "approved_statuses": APPROVED_REVIEW_STATUSES,
    }
    if limit is not None:
        params["limit"] = limit
    with get_engine().connect() as connection:
        return [
            dict(row)
            for row in connection.execute(statement, params).mappings()
            if _approved_http_url(row.get("url"))
        ]


def _chunk_text(row: dict[str, object]) -> str:
    value = row.get("full_text")
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError("knowledge chunk has no usable full_text")


def _content_hash(row: dict[str, object]) -> str:
    """Use the loader's normalized text hash, with a stable local fallback."""
    for field in ("text_hash", "normalised_content_hash", "raw_content_hash"):
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return hashlib.sha256(_chunk_text(row).encode("utf-8")).hexdigest()


def _approved_http_url(value: object) -> bool:
    return isinstance(value, str) and value.startswith(("https://", "http://"))


def _batches(items: Sequence[dict[str, object]], size: int) -> list[Sequence[dict[str, object]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _write_batch(rows: Sequence[dict[str, object]], vectors: Sequence[Sequence[float]]) -> None:
    model = get_settings().gemini_embedding_model
    statement = text(
        """
        UPDATE knowledge_chunks
        SET embedding = :embedding,
            embedding_model = :embedding_model,
            embedded_text_hash = :embedded_text_hash,
            embedded_at = UTC_TIMESTAMP()
        WHERE chunk_id = :chunk_id
        """
    )
    payload = [
        {
            "chunk_id": row["chunk_id"],
            # TiDB's VECTOR column accepts this vector literal via the bound string.
            "embedding": json.dumps(list(vector), separators=(",", ":")),
            "embedding_model": model,
            "embedded_text_hash": _content_hash(row),
        }
        for row, vector in zip(rows, vectors, strict=True)
    ]
    with get_engine().begin() as connection:
        connection.execute(statement, payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="call Gemini and write embeddings")
    parser.add_argument("--batch-size", type=int, default=5, help="Gemini inputs per request (default: 5)")
    parser.add_argument("--limit", type=int, default=None, help="at most this many pending chunks")
    args = parser.parse_args()
    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")

    rows = _pending_rows(args.limit)
    print(f"Pending current chunks for {get_settings().gemini_embedding_model}: {len(rows)}")
    if not args.apply or not rows:
        print("Dry run only; no Gemini calls or database writes were made." if not args.apply else "Nothing to backfill.")
        return

    service = GeminiEmbeddingService()
    written = 0
    for batch in _batches(rows, args.batch_size):
        try:
            vectors = service.embed_many([_chunk_text(row) for row in batch])
        except EmbeddingUnavailable as exc:
            print(f"STOPPED after {written} chunk(s): {exc}", file=sys.stderr)
            print("Re-run the same command later; completed rows are skipped.", file=sys.stderr)
            sys.exit(2)
        _write_batch(batch, vectors)
        written += len(batch)
        print(f"Embedded {written}/{len(rows)} chunk(s)")
    print(f"PASS: embedded {written} chunk(s).")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}. Embedding backfill did not complete.", file=sys.stderr)
        sys.exit(1)
