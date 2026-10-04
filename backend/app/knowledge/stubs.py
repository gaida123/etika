"""STUB: replaced by Developer 1.

Placeholder registry and retrieval services used when ``USE_STUBS=true``. They satisfy the
``RegistryService`` and ``RetrievalService`` protocols in ``app.contracts.services`` so that
Developer 2 can build agents before TiDB retrieval exists. All evidence text is fake.
"""

import json
from pathlib import Path
from typing import Any

from app.contracts.registry import Area, Requirement
from app.contracts.retrieval import RetrievalRequest, RetrievalResult, RetrievedChunk
from app.core.settings import BACKEND_DIR

REGISTRY_PATH = BACKEND_DIR / "data" / "registry" / "requirements.json"
STUB_CHUNKS_PATH = Path(__file__).with_name("stub_chunks.json")

PLACEHOLDER_URL = "TODO-official-url"
PLACEHOLDER_VERSION = "stub"


def load_requirements(path: Path = REGISTRY_PATH) -> list[Requirement]:
    """STUB: replaced by Developer 1. Reads the registry JSON instead of the TiDB table."""
    rows: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return [Requirement.model_validate(row) for row in rows]


class StubRegistryService:
    """STUB: replaced by Developer 1. In-memory registry loaded from requirements.json."""

    def __init__(self, path: Path = REGISTRY_PATH) -> None:
        self._by_id: dict[str, Requirement] = {r.id: r for r in load_requirements(path)}

    def get(self, requirement_id: str) -> Requirement | None:
        return self._by_id.get(requirement_id)

    def list_by_area(self, area: Area) -> list[Requirement]:
        return [r for r in self._by_id.values() if r.area == area]

    def all(self) -> list[Requirement]:
        """All requirements in registry order (stub convenience, not part of the protocol)."""
        return list(self._by_id.values())


class StubRetrievalService:
    """STUB: replaced by Developer 1. Returns placeholder chunks from stub_chunks.json.

    Matches on ``requirement_ids`` (or ``area`` if no IDs are given). Unknown requirement IDs
    return ``insufficient_evidence``. No search, no embeddings.
    """

    def __init__(self, path: Path = STUB_CHUNKS_PATH) -> None:
        self._rows: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        if request.requirement_ids:
            wanted = set(request.requirement_ids)
            rows = [r for r in self._rows if wanted & set(r["requirement_ids"])]
        elif request.area:
            rows = [r for r in self._rows if r["area"] == request.area]
        else:
            rows = []
        rows = rows[: request.limit]

        filters = {
            "jurisdiction_ids": request.jurisdiction_ids,
            "segment_id": request.segment_id,
            "area": request.area,
            "requirement_ids": request.requirement_ids,
            "as_of": request.as_of.isoformat(),
        }
        limitations = ["STUB retrieval: placeholder text, not official sources."]
        if not rows:
            return RetrievalResult(
                status="insufficient_evidence",
                chunks=[],
                query_used=request.query,
                filters_applied=filters,
                limitations=limitations + ["No evidence found for this request."],
            )
        return RetrievalResult(
            status="supported",
            chunks=[_to_chunk(r) for r in rows],
            query_used=request.query,
            filters_applied=filters,
            limitations=limitations,
        )


def _to_chunk(row: dict[str, Any]) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=row["chunk_id"],
        source_id=row["source_id"],
        text=row["text"],
        title=row["title"],
        section_path=row.get("section_path"),
        url=PLACEHOLDER_URL,
        source_version=PLACEHOLDER_VERSION,
        effective_from=None,
        effective_to=None,
        score=None,
    )
