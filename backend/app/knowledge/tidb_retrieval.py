"""Read-only TiDB retrieval for the existing ``knowledge_chunks`` corpus.

The current corpus predates the application's ORM models, so this module reads its
established table directly instead of attempting to own or migrate it.  It is
deliberately a lexical fallback. When enabled after the vector migration, TiDB
also ranks the same filtered corpus by cosine distance without changing the public
retrieval contract.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Collection, Mapping, Sequence
from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.contracts.retrieval import RetrievalRequest, RetrievalResult, RetrievedChunk
from app.core.db import get_engine
from app.core.settings import get_settings
from app.knowledge.embeddings import EmbeddingProvider, EmbeddingUnavailable, GeminiEmbeddingService


# The research workflow should set one of these values only after the owner has
# reviewed the source.  More statuses can be supplied explicitly if the workflow
# uses a different approved label.
DEFAULT_APPROVED_REVIEW_STATUSES = frozenset(
    {"approved", "approved_by_research_owner", "research_owner_approved"}
)

_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "at",
        "be",
        "can",
        "do",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "what",
        "when",
        "where",
        "who",
        "with",
        "you",
        "your",
    }
)


class TiDBRetrievalService:
    """Retrieve official evidence from ``knowledge_chunks`` without modifying it.

    ``bind`` is injectable for tests and scripts.  With no argument, the service uses
    the application's shared TiDB engine.  A SQLAlchemy ``Engine``, ``Connection``,
    ``Session``, or callable returning a ``Session`` is accepted.

    Until TiDB full-text/vector indexes are added, rows are metadata-filtered first and
    then ranked in Python by lexical overlap.  The current corpus is small enough for
    this staging path; it must not be mistaken for final semantic retrieval.
    """

    def __init__(
        self,
        bind: Engine | Connection | Session | Callable[[], Session] | None = None,
        *,
        allow_unreviewed: bool | None = None,
        allow_candidate_requirement_mappings: bool | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        use_semantic: bool | None = None,
        approved_review_statuses: Collection[str] = DEFAULT_APPROVED_REVIEW_STATUSES,
    ) -> None:
        settings = get_settings()
        self._bind = bind if bind is not None else get_engine()
        self._allow_unreviewed = (
            settings.allow_unreviewed_knowledge if allow_unreviewed is None else allow_unreviewed
        )
        self._allow_candidate_requirement_mappings = (
            settings.allow_candidate_requirement_mappings
            if allow_candidate_requirement_mappings is None
            else allow_candidate_requirement_mappings
        )
        self._use_semantic = (
            settings.use_tidb_semantic_retrieval if use_semantic is None else use_semantic
        )
        self._embedding_provider = embedding_provider
        if self._use_semantic and self._embedding_provider is None:
            self._embedding_provider = GeminiEmbeddingService()
        self._approved_review_statuses = frozenset(
            status.strip().casefold() for status in approved_review_statuses if status.strip()
        )
        if not self._approved_review_statuses:
            raise ValueError("approved_review_statuses must contain at least one status")

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Return filtered evidence, or an explicit insufficient-evidence result.

        A requirement-scoped request is eligible only when a chunk maps to that
        requirement.  Candidate mappings are considered only when the explicit staging
        switch is enabled.  An unscoped request needs lexical query overlap so that a
        random query does not receive every chunk in the requested area.
        """
        filters = self._filters(request)
        limitations = self._base_limitations()
        if request.limit <= 0:
            return self._insufficient(request, filters, limitations + ["The requested result limit is zero."])
        if not request.jurisdiction_ids:
            return self._insufficient(
                request,
                filters,
                limitations + ["No jurisdiction IDs were supplied, so no evidence was eligible."],
            )

        semantic_enabled = False
        try:
            if self._use_semantic and not self._semantic_coverage_is_complete(request.area):
                # A partial backfill must never hide evidence that has not yet received
                # a vector. Keep the known-safe lexical ranking until this area is complete.
                candidates = self._load_candidates(request.area)
                limitations.append(
                    "Vector backfill is incomplete for this area; lexical fallback was used."
                )
            else:
                query_embedding = self._query_embedding(request.query)
                semantic_enabled = query_embedding is not None
                candidates = self._load_candidates(request.area, query_embedding)
                if semantic_enabled and not candidates:
                    semantic_enabled = False
                    candidates = self._load_candidates(request.area)
                    limitations.append(
                        "No matching vector-backed chunks were available; lexical fallback was used."
                    )
        except (EmbeddingUnavailable, SQLAlchemyError, ValueError):
            # A temporary Gemini 429 or a partially deployed vector migration must
            # not turn a grounded evidence request into an application error.
            candidates = self._load_candidates(request.area)
            limitations.append(
                "Semantic TiDB ranking was unavailable for this request; lexical fallback was used."
            )
        if semantic_enabled:
            filters["ranking"] = "semantic_vector"
            limitations[0] = "TiDB cosine-distance semantic ranking is in use."
        requested_jurisdictions = set(request.jurisdiction_ids)
        requested_requirements = set(request.requirement_ids)
        as_of = _normalise_datetime(request.as_of)
        ranked_mapped: list[tuple[float, int, str, RetrievedChunk]] = []
        ranked_candidates: list[tuple[float, int, str, RetrievedChunk]] = []
        skipped_invalid_dates = 0

        for row in candidates:
            if not _is_current(row.get("is_current")):
                continue
            if not self._review_is_eligible(row.get("review_status")):
                continue
            if not requested_jurisdictions.intersection(_json_string_list(row.get("jurisdiction_ids"))):
                continue
            is_current_for_date, has_invalid_date = _is_effective_as_of(row, as_of)
            if has_invalid_date:
                skipped_invalid_dates += 1
            if not is_current_for_date:
                continue
            mapping_kind = "unscoped"
            if requested_requirements:
                mapping_kind = self._requirement_match_kind(row, requested_requirements)
                if mapping_kind is None:
                    continue

            chunk = _row_to_chunk(row)
            lexical_score, matched_terms = _lexical_score(request.query, chunk)
            # Requirement mappings are the authoritative scope signal for agent calls.
            # For an exploratory/unscoped request, require actual lexical evidence.
            if not requested_requirements and not _has_enough_lexical_overlap(
                matched_terms, _query_terms(request.query)
            ):
                continue
            score = _semantic_score(row.get("semantic_distance")) if semantic_enabled else lexical_score
            if score is None:
                # A null distance should never happen after ``embedding IS NOT NULL``;
                # do not silently turn it into a high-ranking result.
                continue
            chunk = chunk.model_copy(update={"score": score})
            ordinal = _as_int(row.get("chunk_ordinal"))
            ranked_item = (score, ordinal, chunk.chunk_id, chunk)
            if mapping_kind == "candidate":
                ranked_candidates.append(ranked_item)
            else:
                ranked_mapped.append(ranked_item)

        if skipped_invalid_dates:
            limitations.append(
                f"Skipped {skipped_invalid_dates} chunk(s) with an unreadable effective date."
            )
        # Candidate IDs are research leads, not final evidence mappings.  They may fill
        # a staging gap only when no eligible finalized mapping exists for this request.
        use_candidate_fallback = bool(requested_requirements and not ranked_mapped and ranked_candidates)
        ranked = ranked_mapped if ranked_mapped else ranked_candidates
        if use_candidate_fallback:
            filters["candidate_mapping_fallback_used"] = True
            limitations.append(
                "No finalized requirement mapping was eligible; staging candidate mappings supplied this evidence."
            )
        else:
            filters["candidate_mapping_fallback_used"] = False
        ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
        chunks = [chunk for _, _, _, chunk in ranked[: request.limit]]
        if not chunks:
            return self._insufficient(
                request,
                filters,
                limitations + ["No evidence matched the requested metadata filters and query."],
            )
        return RetrievalResult(
            status="supported",
            chunks=chunks,
            query_used=request.query,
            filters_applied=filters,
            limitations=limitations,
        )

    def _query_embedding(self, query: str) -> list[float] | None:
        if not self._use_semantic:
            return None
        if self._embedding_provider is None:
            raise EmbeddingUnavailable("Semantic embedding provider is not configured")
        return self._embedding_provider.embed(query)

    def _semantic_coverage_is_complete(self, area: str | None) -> bool:
        """Require vectors for every current chunk before semantic ranking is enabled.

        This prevents an in-progress model migration/backfill from returning only the
        subset that happens to have embeddings and incorrectly calling it complete.
        """
        statement = """
            SELECT
                COUNT(*) AS total_count,
                SUM(
                    CASE WHEN embedding IS NOT NULL AND embedding_model = :embedding_model
                    THEN 1 ELSE 0 END
                ) AS embedded_count
            FROM knowledge_chunks
            WHERE is_current = :is_current
        """
        params: dict[str, Any] = {
            "is_current": True,
            "embedding_model": self._embedding_provider.model if self._embedding_provider else "",
        }
        if area:
            statement += " AND area = :area"
            params["area"] = area
        rows = self._execute_mappings(text(statement), params)
        if not rows:
            return False
        total = _as_int(rows[0].get("total_count"))
        embedded = _as_int(rows[0].get("embedded_count"))
        return total > 0 and total == embedded

    def _load_candidates(
        self, area: str | None, query_embedding: Sequence[float] | None = None
    ) -> list[Mapping[str, Any]]:
        """Read candidates, optionally ranked by TiDB cosine distance.

        Metadata constraints are enforced again in Python below so an approximate
        vector index can never bypass the evidence gates.
        """
        semantic_select = ""
        semantic_where = ""
        semantic_order = ""
        params: dict[str, Any] = {"is_current": True}
        if query_embedding is not None:
            # TiDB accepts a JSON-like vector string and validates it against the
            # fixed VECTOR(3072) column. Binding prevents query-vector SQL injection.
            semantic_select = ",\n                VEC_COSINE_DISTANCE(embedding, :query_embedding) AS semantic_distance"
            semantic_where = "\n              AND embedding IS NOT NULL\n              AND embedding_model = :embedding_model"
            semantic_order = "\n            ORDER BY semantic_distance ASC"
            params["query_embedding"] = json.dumps(list(query_embedding), separators=(",", ":"))
            params["embedding_model"] = self._embedding_provider.model if self._embedding_provider else ""
        statement = f"""
            SELECT
                chunk_id,
                source_id,
                source_title,
                url,
                section_path,
                body_text,
                full_text,
                jurisdiction_ids,
                area,
                candidate_requirement_ids,
                mapped_requirement_ids,
                review_status,
                source_version,
                effective_from,
                effective_to,
                is_current,
                chunk_ordinal{semantic_select}
            FROM knowledge_chunks
            WHERE is_current = :is_current
            {semantic_where}
        """
        if area:
            statement += " AND area = :area"
            params["area"] = area
        statement += semantic_order
        return self._execute_mappings(text(statement), params)

    def _execute_mappings(self, statement: Any, params: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        """Execute a SELECT while respecting the lifecycle of an injected bind."""
        bind = self._bind
        if isinstance(bind, Engine):
            with bind.connect() as connection:
                return [dict(row) for row in connection.execute(statement, params).mappings()]
        if isinstance(bind, Connection):
            return [dict(row) for row in bind.execute(statement, params).mappings()]
        if isinstance(bind, Session):
            return [dict(row) for row in bind.execute(statement, params).mappings()]
        if callable(bind):
            with bind() as session:
                return [dict(row) for row in session.execute(statement, params).mappings()]
        raise TypeError("bind must be a SQLAlchemy Engine, Connection, Session, or session factory")

    def _review_is_eligible(self, review_status: object) -> bool:
        if self._allow_unreviewed:
            return True
        return isinstance(review_status, str) and review_status.strip().casefold() in self._approved_review_statuses

    def _requirement_match_kind(
        self, row: Mapping[str, Any], requested_requirement_ids: set[str]
    ) -> str | None:
        """Classify a mapping, preferring finalized IDs over candidate research leads."""
        mapped = set(_json_string_list(row.get("mapped_requirement_ids")))
        if mapped.intersection(requested_requirement_ids):
            return "mapped"
        if not self._allow_candidate_requirement_mappings:
            return None
        candidates = set(_json_string_list(row.get("candidate_requirement_ids")))
        return "candidate" if candidates.intersection(requested_requirement_ids) else None

    def _filters(self, request: RetrievalRequest) -> dict[str, Any]:
        """Make all applied and unavailable filters auditable in the response."""
        return {
            "jurisdiction_ids": request.jurisdiction_ids,
            "segment_id": request.segment_id,
            "segment_filter_applied": False,
            "area": request.area,
            "requirement_ids": request.requirement_ids,
            "as_of": _normalise_datetime(request.as_of).isoformat(),
            "is_current": True,
            "approved_review_statuses": sorted(self._approved_review_statuses),
            "allow_unreviewed": self._allow_unreviewed,
            "allow_candidate_requirement_mappings": self._allow_candidate_requirement_mappings,
            "candidate_mapping_fallback_used": False,
            "ranking": "lexical_fallback",
            "embedding_model": self._embedding_provider.model
            if self._use_semantic and self._embedding_provider
            else None,
        }

    def _base_limitations(self) -> list[str]:
        limitations = [
            "Lexical fallback retrieval is in use; semantic TiDB ranking is disabled or unavailable.",
            "The current knowledge_chunks schema has no segment_id field, so segment filtering was not applied.",
        ]
        if self._allow_unreviewed:
            limitations.append(
                "Unreviewed knowledge is enabled for staging; research-owner review is still required."
            )
        if self._allow_candidate_requirement_mappings:
            limitations.append(
                "Candidate requirement mappings are enabled for staging; finalized mappings take precedence."
            )
        return limitations

    @staticmethod
    def _insufficient(
        request: RetrievalRequest,
        filters: dict[str, Any],
        limitations: list[str],
    ) -> RetrievalResult:
        return RetrievalResult(
            status="insufficient_evidence",
            chunks=[],
            query_used=request.query,
            filters_applied=filters,
            limitations=limitations,
        )


def _row_to_chunk(row: Mapping[str, Any]) -> RetrievedChunk:
    """Map one pre-existing corpus row to the stable app contract."""
    body_text = _as_nonempty_string(row.get("body_text"))
    text_value = body_text or _as_nonempty_string(row.get("full_text"))
    section_path = _section_path(row.get("section_path"))
    return RetrievedChunk(
        chunk_id=_required_string(row.get("chunk_id"), "chunk_id"),
        source_id=_required_string(row.get("source_id"), "source_id"),
        text=_required_string(text_value, "body_text/full_text"),
        title=_required_string(row.get("source_title"), "source_title"),
        section_path=section_path,
        url=_required_string(row.get("url"), "url"),
        source_version=_as_nonempty_string(row.get("source_version")) or "unknown",
        effective_from=_parse_effective_datetime(row.get("effective_from"), end_of_day=False)[0],
        effective_to=_parse_effective_datetime(row.get("effective_to"), end_of_day=True)[0],
        score=None,
    )


def _lexical_score(query: str, chunk: RetrievedChunk | str) -> tuple[float, set[str]]:
    """Return query-term coverage and matched terms, without making a legal inference."""
    terms = _query_terms(query)
    if not terms:
        return 0.0, set()
    if isinstance(chunk, RetrievedChunk):
        haystack = " ".join(
            value for value in (chunk.title, chunk.section_path or "", chunk.text) if value
        ).casefold()
    else:
        haystack = chunk.casefold()
    haystack_terms = set(_TOKEN_RE.findall(haystack))
    matched = terms.intersection(haystack_terms)
    return len(matched) / len(terms), matched


def _query_terms(query: str) -> set[str]:
    return {
        token
        for token in (part.casefold() for part in _TOKEN_RE.findall(query))
        if len(token) > 1 and token not in _STOP_WORDS
    }


def _has_enough_lexical_overlap(matched_terms: set[str], query_terms: set[str]) -> bool:
    """Avoid returning broad area results for an unrelated exploratory query."""
    if not query_terms:
        return False
    minimum_terms = 1 if len(query_terms) == 1 else 2
    return len(matched_terms) >= minimum_terms


def _json_string_list(value: object) -> list[str]:
    """Accept TiDB JSON strings plus deserialized values used by SQLite/tests."""
    if value is None:
        return []
    decoded = value
    if isinstance(value, (bytes, bytearray)):
        try:
            decoded = value.decode("utf-8")
        except UnicodeDecodeError:
            return []
    if isinstance(decoded, str):
        try:
            decoded = json.loads(decoded)
        except json.JSONDecodeError:
            return []
    if not isinstance(decoded, Sequence) or isinstance(decoded, (str, bytes, bytearray)):
        return []
    return [item.strip() for item in decoded if isinstance(item, str) and item.strip()]


def _section_path(value: object) -> str | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return value.strip() or None
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        parts = [str(part).strip() for part in value if str(part).strip()]
        return " > ".join(parts) or None
    return None


def _is_effective_as_of(row: Mapping[str, Any], as_of: datetime) -> tuple[bool, bool]:
    effective_from, bad_from = _parse_effective_datetime(row.get("effective_from"), end_of_day=False)
    effective_to, bad_to = _parse_effective_datetime(row.get("effective_to"), end_of_day=True)
    if bad_from or bad_to:
        return False, True
    if effective_from is not None and effective_from > as_of:
        return False, False
    if effective_to is not None and effective_to < as_of:
        return False, False
    return True, False


def _parse_effective_datetime(value: object, *, end_of_day: bool) -> tuple[datetime | None, bool]:
    """Parse the corpus's ISO/date string fields, treating date-only end dates inclusively."""
    if value is None:
        return None, False
    if isinstance(value, datetime):
        return _normalise_datetime(value), False
    if isinstance(value, date):
        parsed_time = time.max if end_of_day else time.min
        return datetime.combine(value, parsed_time, tzinfo=UTC), False
    if not isinstance(value, str) or not value.strip():
        return None, False
    raw = value.strip()
    try:
        if "T" not in raw and " " not in raw:
            parsed_date = date.fromisoformat(raw)
            parsed_time = time.max if end_of_day else time.min
            return datetime.combine(parsed_date, parsed_time, tzinfo=UTC), False
        return _normalise_datetime(datetime.fromisoformat(raw.replace("Z", "+00:00"))), False
    except ValueError:
        return None, True


def _normalise_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _required_string(value: object, name: str) -> str:
    result = _as_nonempty_string(value)
    if result is None:
        raise ValueError(f"knowledge_chunks row has no usable {name}")
    return result


def _as_nonempty_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _semantic_score(value: object) -> float | None:
    """Convert TiDB cosine distance (lower is better) to a descending score."""
    try:
        distance = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return 1.0 - distance if math.isfinite(distance) else None


def _is_current(value: object) -> bool:
    return value is True or value == 1 or (isinstance(value, str) and value.casefold() in {"1", "true"})
