"""Focused contract tests for the read-only TiDB knowledge adapter.

SQLite is intentional here: the adapter keeps JSON filtering/ranking in Python so the
same tests exercise the TiDB row mapping without requiring a live cloud connection.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import Boolean, Column, Integer, JSON, MetaData, String, Table, Text, text
from sqlalchemy.engine import Engine

from app.contracts.retrieval import RetrievalRequest
from app.core.db import make_engine
from app.knowledge.tidb_retrieval import TiDBRetrievalService, _semantic_score


@pytest.fixture
def corpus_engine() -> Engine:
    engine = make_engine("sqlite://")
    metadata = MetaData()
    chunks = Table(
        "knowledge_chunks",
        metadata,
        Column("chunk_id", String, primary_key=True),
        Column("source_id", String, nullable=False),
        Column("chunk_ordinal", Integer, nullable=False),
        Column("source_title", Text, nullable=False),
        Column("url", Text, nullable=False),
        Column("section_path", JSON, nullable=True),
        Column("body_text", Text, nullable=True),
        Column("full_text", Text, nullable=True),
        Column("jurisdiction_ids", JSON, nullable=False),
        Column("area", String, nullable=False),
        Column("candidate_requirement_ids", JSON, nullable=False),
        Column("mapped_requirement_ids", JSON, nullable=False),
        Column("review_status", String, nullable=False),
        Column("source_version", Text, nullable=True),
        Column("effective_from", String, nullable=True),
        Column("effective_to", String, nullable=True),
        Column("is_current", Boolean, nullable=False),
        Column("embedding", String, nullable=True),
        Column("embedding_model", String, nullable=True),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            chunks.insert(),
            [
                _row(
                    "mapped-approved",
                    source_id="bc-pst-small-sellers",
                    title="PST small seller exemption",
                    body="Small sellers need not register for BC PST under the stated conditions.",
                    mapped=["TAX-01"],
                    effective_from="2026-01-01",
                ),
                _row(
                    "candidate-pending",
                    source_id="bc-pst-small-sellers",
                    title="PST small seller registration",
                    body="A BC small seller should review the PST registration threshold.",
                    candidate=["TAX-99"],
                    review_status="pending_research_owner_review",
                    ordinal=2,
                ),
                _row(
                    "candidate-when-mapped-exists",
                    source_id="bc-pst-small-sellers",
                    title="PST small seller candidate",
                    body="Candidate-only PST material that must not displace a finalized mapping.",
                    candidate=["TAX-01"],
                    review_status="pending_research_owner_review",
                    ordinal=3,
                ),
                _row(
                    "expired-mapped",
                    source_id="old-pst",
                    title="Old PST rule",
                    body="Old PST small seller rule.",
                    mapped=["TAX-01"],
                    effective_to="2025-12-31",
                    ordinal=4,
                ),
                _row(
                    "future-mapped",
                    source_id="future-pst",
                    title="Future PST rule",
                    body="Future PST small seller rule.",
                    mapped=["TAX-01"],
                    effective_from="2027-01-01",
                    ordinal=5,
                ),
                _row(
                    "wrong-jurisdiction",
                    source_id="ontario-pst",
                    title="Other province tax rule",
                    body="Other province tax material.",
                    mapped=["TAX-01"],
                    jurisdictions=["CA-ON"],
                    ordinal=6,
                ),
                _row(
                    "stale-source",
                    source_id="stale-pst",
                    title="Stale PST rule",
                    body="Stale PST small seller rule.",
                    mapped=["TAX-01"],
                    is_current=False,
                    ordinal=7,
                ),
            ],
        )
    return engine


def _row(
    chunk_id: str,
    *,
    source_id: str,
    title: str,
    body: str,
    mapped: list[str] | None = None,
    candidate: list[str] | None = None,
    review_status: str = "approved",
    jurisdictions: list[str] | None = None,
    effective_from: str | None = None,
    effective_to: str | None = None,
    is_current: bool = True,
    ordinal: int = 1,
) -> dict[str, object]:
    return {
        "chunk_id": chunk_id,
        "source_id": source_id,
        "chunk_ordinal": ordinal,
        "source_title": title,
        "url": f"https://example.test/{source_id}",
        "section_path": ["PST", "Small sellers"],
        "body_text": body,
        "full_text": f"{title}\n{body}",
        "jurisdiction_ids": jurisdictions or ["CA-BC"],
        "area": "tax",
        "candidate_requirement_ids": candidate or [],
        "mapped_requirement_ids": mapped or [],
        "review_status": review_status,
        "source_version": "2026-01-01",
        "effective_from": effective_from,
        "effective_to": effective_to,
        "is_current": is_current,
    }


def _request(*, requirement_ids: list[str] | None = None, query: str = "BC PST small seller") -> RetrievalRequest:
    return RetrievalRequest(
        query=query,
        jurisdiction_ids=["CA", "CA-BC", "CA-BC-VANCOUVER"],
        segment_id="home_online_sole_prop",
        area="tax",
        requirement_ids=requirement_ids or [],
        as_of=datetime(2026, 10, 4, tzinfo=UTC),
        limit=5,
    )


def test_retrieves_only_current_approved_mapped_evidence(corpus_engine: Engine) -> None:
    service = TiDBRetrievalService(corpus_engine)

    result = service.retrieve(_request(requirement_ids=["TAX-01"]))

    assert result.status == "supported"
    assert [chunk.chunk_id for chunk in result.chunks] == ["mapped-approved"]
    chunk = result.chunks[0]
    assert chunk.text.startswith("Small sellers")
    assert chunk.section_path == "PST > Small sellers"
    assert chunk.effective_from == datetime(2026, 1, 1, tzinfo=UTC)
    assert chunk.score and chunk.score > 0
    assert result.filters_applied["segment_filter_applied"] is False
    assert result.filters_applied["candidate_mapping_fallback_used"] is False


def test_candidate_mappings_are_used_only_when_no_final_mapping_is_eligible(corpus_engine: Engine) -> None:
    service = TiDBRetrievalService(
        corpus_engine,
        allow_unreviewed=True,
        allow_candidate_requirement_mappings=True,
    )

    mapped_result = service.retrieve(_request(requirement_ids=["TAX-01"]))
    assert [chunk.chunk_id for chunk in mapped_result.chunks] == ["mapped-approved"]
    assert mapped_result.filters_applied["candidate_mapping_fallback_used"] is False
    candidate_result = service.retrieve(_request(requirement_ids=["TAX-99"]))
    assert candidate_result.status == "supported"
    assert [chunk.chunk_id for chunk in candidate_result.chunks] == ["candidate-pending"]
    assert candidate_result.filters_applied["candidate_mapping_fallback_used"] is True
    assert any("No finalized requirement mapping" in item for item in candidate_result.limitations)


def test_unreviewed_or_candidate_rows_are_rejected_by_default(corpus_engine: Engine) -> None:
    service = TiDBRetrievalService(corpus_engine)

    result = service.retrieve(_request(requirement_ids=["TAX-99"]))

    assert result.status == "insufficient_evidence"
    assert result.chunks == []


def test_unscoped_unknown_query_does_not_return_broad_area_evidence(corpus_engine: Engine) -> None:
    service = TiDBRetrievalService(corpus_engine)

    result = service.retrieve(_request(query="interplanetary moon permit"))

    assert result.status == "insufficient_evidence"
    assert result.chunks == []


def test_retrieve_many_preserves_request_order_and_all_filters(corpus_engine: Engine) -> None:
    service = TiDBRetrievalService(
        corpus_engine,
        allow_unreviewed=True,
        allow_candidate_requirement_mappings=True,
    )
    requests = [_request(requirement_ids=["TAX-99"]), _request(requirement_ids=["TAX-01"])]

    results = service.retrieve_many(requests)

    assert [result.query_used for result in results] == [request.query for request in requests]
    assert [[chunk.chunk_id for chunk in result.chunks] for result in results] == [
        ["candidate-pending"],
        ["mapped-approved"],
    ]
    for request, result in zip(requests, results, strict=True):
        assert result.filters_applied["jurisdiction_ids"] == request.jurisdiction_ids
        assert result.filters_applied["segment_id"] == request.segment_id
        assert result.filters_applied["area"] == request.area
        assert result.filters_applied["requirement_ids"] == request.requirement_ids


def test_knowledge_base_version_changes_with_current_source_version(corpus_engine: Engine) -> None:
    service = TiDBRetrievalService(corpus_engine)

    initial = service.knowledge_base_version()
    with corpus_engine.begin() as connection:
        connection.execute(
            text("UPDATE knowledge_chunks SET source_version = :version WHERE chunk_id = :chunk_id"),
            {"version": "2026-10-05", "chunk_id": "mapped-approved"},
        )

    assert len(initial) == 64
    assert service.knowledge_base_version() != initial


def test_semantic_distance_is_converted_to_descending_score() -> None:
    assert _semantic_score(0.0) == 1.0
    assert _semantic_score("0.25") == 0.75
    assert _semantic_score(None) is None
    assert _semantic_score(float("nan")) is None


class _FakeEmbeddingProvider:
    model = "test-embedding-model"

    def embed(self, text: str) -> list[float]:
        return [0.1, 0.2]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class _BatchEmbeddingProvider(_FakeEmbeddingProvider):
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return super().embed_many(texts)


class _SemanticBatchService(TiDBRetrievalService):
    """Avoid TiDB vector SQL in SQLite while exercising the batch planning contract."""

    def __init__(self, provider: _BatchEmbeddingProvider) -> None:
        super().__init__("not-a-bind", use_semantic=True, embedding_provider=provider)
        self.embeddings_seen: list[list[float] | None] = []

    def _semantic_coverage_is_complete(self, area: str | None) -> bool:
        return True

    def _load_candidates(
        self, area: str | None, query_embedding: list[float] | None = None
    ) -> list[dict[str, object]]:
        self.embeddings_seen.append(query_embedding)
        return [
            _row(
                "semantic-mapped",
                source_id="semantic-source",
                title="PST small seller exemption",
                body="Small sellers need not register for BC PST.",
                mapped=["TAX-01"],
            )
            | ({"semantic_distance": 0.1} if query_embedding is not None else {})
        ]


def test_partial_vector_backfill_uses_lexical_fallback(corpus_engine: Engine) -> None:
    service = TiDBRetrievalService(
        corpus_engine,
        use_semantic=True,
        embedding_provider=_FakeEmbeddingProvider(),
    )

    result = service.retrieve(_request(requirement_ids=["TAX-01"]))

    assert result.status == "supported"
    assert result.filters_applied["ranking"] == "lexical_fallback"
    assert any("Vector backfill is incomplete" in item for item in result.limitations)


def test_retrieve_many_batches_semantic_query_embeddings() -> None:
    provider = _BatchEmbeddingProvider()
    service = _SemanticBatchService(provider)
    requests = [
        _request(requirement_ids=["TAX-01"], query="BC PST small seller"),
        _request(requirement_ids=["TAX-01"], query="PST registration exemption"),
    ]

    results = service.retrieve_many(requests)

    assert provider.calls == [[request.query for request in requests]]
    assert service.embeddings_seen == [[0.1, 0.2], [0.1, 0.2]]
    assert [result.filters_applied["ranking"] for result in results] == [
        "semantic_vector",
        "semantic_vector",
    ]
