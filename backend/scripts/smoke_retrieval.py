"""Read-only smoke test for the live TiDB knowledge retrieval service.

Run from ``backend/``:

    python scripts/smoke_retrieval.py

This script does not write to TiDB. It exercises the real
``TiDBRetrievalService`` directly (rather than the application service factory)
so it remains useful while the registry, applicability, calculator, and scoring
services are still stubs. When ``USE_TIDB_SEMANTIC_RETRIEVAL=true``, it makes one
Gemini embedding call per test query and asserts TiDB vector ranking was used.

The positive TAX-01 case relies on the development corpus gates in ``.env``:
``ALLOW_UNREVIEWED_KNOWLEDGE=true`` and
``ALLOW_CANDIDATE_REQUIREMENT_MAPPINGS=true``.  Leave both false in a
production deployment until research review and requirement mappings are
complete.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.contracts.facts import DEFAULT_SEGMENT_ID  # noqa: E402
from app.contracts.retrieval import RetrievalRequest, RetrievalResult  # noqa: E402
from app.core.settings import get_settings  # noqa: E402
from app.knowledge.tidb_retrieval import TiDBRetrievalService  # noqa: E402


JURISDICTIONS = ["CA", "CA-BC", "CA-BC-VANCOUVER"]
PST_SOURCE_ID = "bc-pst-small-sellers"
POSITIVE_CASE = RetrievalRequest(
    query="BC PST small seller registration requirements",
    jurisdiction_ids=JURISDICTIONS,
    segment_id=DEFAULT_SEGMENT_ID,
    area="tax",
    requirement_ids=["TAX-01"],
    as_of=datetime.now(timezone.utc),
    limit=3,
)
NEGATIVE_CASE = RetrievalRequest(
    query="retrieval smoke probe for a deliberately unknown requirement",
    jurisdiction_ids=JURISDICTIONS,
    segment_id=DEFAULT_SEGMENT_ID,
    area="tax",
    requirement_ids=["NOPE-99"],
    as_of=datetime.now(timezone.utc),
    limit=3,
)
REG_02_GAP_CASE = RetrievalRequest(
    query="City of Vancouver business licence requirements",
    jurisdiction_ids=JURISDICTIONS,
    segment_id=DEFAULT_SEGMENT_ID,
    area="registration",
    requirement_ids=["REG-02"],
    as_of=datetime.now(timezone.utc),
    limit=3,
)


def _print_chunks(label: str, result: RetrievalResult) -> None:
    """Print only public evidence metadata; never print text, settings, or errors."""
    print(f"{label}: {result.status} ({len(result.chunks)} chunk(s))")
    for chunk in result.chunks:
        print(f"  - {chunk.chunk_id}")
        print(f"    source: {chunk.source_id}")
        print(f"    title: {chunk.title}")
        print(f"    url: {chunk.url}")


def _assert_positive(result: RetrievalResult) -> None:
    """Verify that the known PST requirement produces usable source metadata."""
    if result.status != "supported" or not result.chunks:
        raise AssertionError("TAX-01 did not return any supporting evidence")
    if result.query_used != POSITIVE_CASE.query:
        raise AssertionError("retrieval did not preserve the requested query")

    chunk_ids = [chunk.chunk_id for chunk in result.chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise AssertionError("retrieval returned duplicate chunk IDs")
    if PST_SOURCE_ID not in {chunk.source_id for chunk in result.chunks}:
        raise AssertionError("TAX-01 did not include the expected BC PST small-sellers source")
    for chunk in result.chunks:
        if not all((chunk.chunk_id, chunk.source_id, chunk.title, chunk.url)):
            raise AssertionError("a returned chunk is missing required source metadata")


def _assert_ranking(result: RetrievalResult, semantic_expected: bool) -> None:
    expected = "semantic_vector" if semantic_expected else "lexical_fallback"
    if result.filters_applied.get("ranking") != expected:
        raise AssertionError(f"expected {expected} ranking, got {result.filters_applied.get('ranking')!r}")


def _assert_insufficient(result: RetrievalResult, request: RetrievalRequest, case_name: str) -> None:
    """Verify that no evidence leaks through a requirement filter with no mapping."""
    if result.status != "insufficient_evidence" or result.chunks:
        raise AssertionError(f"{case_name} returned evidence; requirement filtering is not safe")
    if result.query_used != request.query:
        raise AssertionError("retrieval did not preserve the requested query")


def main() -> None:
    settings = get_settings()
    mode = "semantic Gemini/TiDB vector" if settings.use_tidb_semantic_retrieval else "lexical fallback"
    print(f"Live TiDB retrieval smoke test ({mode}; read-only)")
    print(f"ALLOW_UNREVIEWED_KNOWLEDGE={settings.allow_unreviewed_knowledge}")
    print(f"ALLOW_CANDIDATE_REQUIREMENT_MAPPINGS={settings.allow_candidate_requirement_mappings}")

    # Construct the live adapter directly: ``get_services()`` may intentionally
    # return the all-stub bundle until the full Dev 1 cutover is ready.
    service = TiDBRetrievalService()
    positive = service.retrieve(POSITIVE_CASE)
    negative = service.retrieve(NEGATIVE_CASE)
    reg_02_gap = service.retrieve(REG_02_GAP_CASE)

    _print_chunks("TAX-01 / BC PST", positive)
    _print_chunks("NOPE-99 / deliberate negative", negative)
    _print_chunks("REG-02 / known evidence gap", reg_02_gap)
    _assert_positive(positive)
    _assert_ranking(positive, settings.use_tidb_semantic_retrieval)
    _assert_insufficient(negative, NEGATIVE_CASE, "NOPE-99")
    _assert_insufficient(reg_02_gap, REG_02_GAP_CASE, "REG-02")
    print("PASS: live retrieval returned PST evidence and rejected both missing-evidence cases.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Do not print a database exception: some drivers include the connection
        # URL in it. The exception type plus this generic message is enough for a
        # safe smoke-test failure, while application logs retain diagnostics.
        print(f"FAILED: {type(exc).__name__}. Live retrieval smoke test did not pass.", file=sys.stderr)
        sys.exit(1)
