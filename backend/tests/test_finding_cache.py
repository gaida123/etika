"""Phase 3: the per-requirement finding cache. Gemini and retrieval are faked; no live calls."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.agents.finding_cache import PROMPT_VERSION, fact_snapshot
from app.contracts.facts import BusinessProfile, FactValue
from app.core.models import FindingCacheRow
from app.core.services import build_stub_services
from app.core.settings import get_settings
from app.knowledge.stubs import StubRetrievalService
from tests.fake_gemini import FakeGemini
from tests.test_agents import assess_maya, use_fake


@pytest.fixture(autouse=True)
def prefetch_mode(agent_mode: Callable[..., None]) -> None:
    agent_mode("prefetch")


def run(client: TestClient, session: Session | None = None, facts: dict[str, FactValue] | None = None) -> tuple[dict, FakeGemini]:
    """One assessment with a fresh counter, so each run's Gemini requests are its own."""
    fake = FakeGemini()
    use_fake(fake)
    return assess_maya(client, session, facts), fake


def explanations(body: dict) -> dict[str, str]:
    return {f["requirement_id"]: f["explanation"] for f in body["findings"]}


def statuses(body: dict) -> dict[str, str]:
    return {f["requirement_id"]: f["status"] for f in body["findings"]}


def cached_per_agent(body: dict) -> dict[str, int]:
    return {a["agent"]: a["cached_findings"] for a in body["agents"]}


# --- the key ----------------------------------------------------------------------------------


def test_snapshot_only_reads_the_facts_a_requirement_depends_on(maya: BusinessProfile) -> None:
    registry = build_stub_services().registry
    emp01 = registry.get("EMP-01")
    reg03 = registry.get("REG-03")
    assert emp01 is not None and reg03 is not None

    assert sorted(fact_snapshot(maya, emp01)) == ["has_employees", "plans_to_hire"]
    # a requirement that declares no dependencies is treated as depending on every fact
    assert sorted(fact_snapshot(maya, reg03)) == sorted(maya.facts)
    # unknown is never cached as false
    assert fact_snapshot(maya, emp01)["plans_to_hire"] is None


# --- the four Phase 3 guarantees ---------------------------------------------------------------


def test_same_facts_zero_calls(client: TestClient) -> None:
    first, first_fake = run(client)
    second, second_fake = run(client)

    assert first_fake.requests == 3  # one report call per agent
    assert second_fake.requests == 0  # every finding came from the cache
    assert second_fake.reports == {}
    assert explanations(second) == explanations(first)
    assert statuses(second) == statuses(first)
    assert cached_per_agent(second) == {"registration": 3, "tax": 4, "employer": 6}

    # Step 3.5: reused claims are still validated against chunks registered on this run
    cited = {f["requirement_id"]: [c["chunk_ids"] for c in f["claims"]] for f in second["findings"]}
    assert cited == {f["requirement_id"]: [c["chunk_ids"] for c in f["claims"]] for f in first["findings"]}
    assert all(ids for lists in cited.values() for ids in lists)
    # and the source links code builds from them survive
    assert [i["sources"] for i in second["now"]] == [i["sources"] for i in first["now"]]


def test_unrelated_fact_keeps_cache(client: TestClient, session: Session) -> None:
    run(client)
    # `sells` is declared only by TAX-01 and TAX-04; nothing in the employer area reads it
    _, fake = run(client, session, {"sells": FactValue(value="services_only", confirmed=True)})

    assert "employer" not in fake.reports  # untouched agent makes no request at all
    assert fake.reports.get("tax") == 1  # one smaller call for the affected tax findings
    assert fake.requests == 2


def test_kb_bump_invalidates(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    run(client)
    monkeypatch.setattr(StubRetrievalService, "knowledge_base_version", lambda self: "stub-v2")

    _, fake = run(client)

    assert fake.requests == 3  # evidence may have changed, so nothing is reused
    assert fake.reports == {"registration": 1, "tax": 1, "employer": 1}


def test_status_never_from_cache(client: TestClient, session: Session) -> None:
    first, _ = run(client)
    rows = list(session.scalars(select(FindingCacheRow)))
    assert rows and all("status" not in row.draft_json for row in rows)
    assert all(row.prompt_version == PROMPT_VERSION for row in rows)

    for row in rows:  # a poisoned entry must not be able to set a status
        row.draft_json = {**row.draft_json, "status": "done", "explanation": "From the cache."}
        flag_modified(row, "draft_json")
    session.commit()

    second, fake = run(client)

    assert fake.requests == 0
    assert set(explanations(second).values()) == {"From the cache."}  # the cache really was used
    assert statuses(second) == statuses(first)  # status still comes from applicability
    assert "done" not in statuses(second).values()


# --- the switch -------------------------------------------------------------------------------


def test_cache_off_pays_for_every_run(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "finding_cache_enabled", False)

    run(client)
    body, fake = run(client)

    assert fake.requests == 3
    assert list(session.scalars(select(FindingCacheRow))) == []  # nothing written, nothing reused
    assert cached_per_agent(body) == {"registration": 0, "tax": 0, "employer": 0}
