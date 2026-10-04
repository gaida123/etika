"""Agents, orchestrator, citation validation and assessment routes (Gemini faked).

These cover the legacy investigate+report path, so every test here pins AGENT_MODE="legacy".
The Phase 2 prefetch path is covered in test_prefetch.py.
"""

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agents.orchestrator import AGENT_UNAVAILABLE_FLAG, Orchestrator, employer_mode
from app.agents.schemas import ClaimDraft, FindingDraft
from app.api.main import app
from app.chat.citations import NO_SOURCE_EXPLANATION, NO_SOURCE_FLAG, validate_citations
from app.contracts.facts import BusinessProfile, FactValue
from app.core.llm import get_content_generator, get_llm
from app.core.services import build_stub_services
from app.intake import profile_service
from app.intake.profile_service import ProfileUpdate
from tests.fake_gemini import INVENTED_CHUNK, FakeGemini


def use_fake(fake: FakeGemini) -> None:
    app.dependency_overrides[get_content_generator] = lambda: fake.generate
    app.dependency_overrides[get_llm] = lambda: fake.structured


@pytest.fixture(autouse=True)
def legacy_mode(agent_mode: Callable[..., None]) -> None:
    agent_mode("legacy")


@pytest.fixture
def fake(client: TestClient) -> Iterator[FakeGemini]:
    fake = FakeGemini()
    use_fake(fake)
    yield fake


def assess_maya(client: TestClient, session: Session | None = None, facts: dict[str, FactValue] | None = None) -> dict:
    business_id = client.post("/dev/load-demo").json()["business_id"]
    if session is not None and facts:
        profile_service.update_facts(session, business_id, ProfileUpdate(facts=facts))
    resp = client.post(f"/assess/{business_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- end to end -------------------------------------------------------------------------------


def test_maya_assessment(client: TestClient, fake: FakeGemini) -> None:
    body = assess_maya(client)

    assert body["score"] == 0.0
    assert [i["requirement_id"] for i in body["now"]] == ["REG-01", "REG-02"]
    assert {a["agent"]: a["mode"] for a in body["agents"]} == {
        "registration": None,
        "tax": None,
        "employer": "pre_hire",
    }
    assert all(a["error"] is None for a in body["agents"])
    assert len(body["findings"]) == 13
    assert body["disclaimer"]

    findings = {f["requirement_id"]: f for f in body["findings"]}
    assert "EMP-99" not in findings
    for f in body["findings"]:
        for claim in f["claims"]:
            assert INVENTED_CHUNK not in claim["chunk_ids"]
    assert findings["REG-01"]["status"] == "not_done"
    assert findings["TAX-01"]["status"] == "not_yet_required"
    assert "Home-based licence rules unclear" in findings["REG-02"]["flags"]

    reg01 = body["now"][0]
    assert reg01["action_url"] == "TODO-official-url"
    assert reg01["sources"] and reg01["sources"][0]["url"] == "TODO-official-url"

    tax01 = next(i for i in body["next"] if i["requirement_id"] == "TAX-01")
    assert tax01["progress"]["current"] == 8200
    assert tax01["progress"]["threshold"] == 10000
    assert tax01["progress"]["estimated_crossing"]


def test_trace_records_every_tool_call(client: TestClient, fake: FakeGemini) -> None:
    body = assess_maya(client)
    trace = client.get(f"/assessments/{body['assessment_id']}/trace").json()

    tools = [(t["agent"], t["tool_name"]) for t in trace]
    assert ("orchestrator", "plan") in tools
    assert ("tax", "get_calculator_result") in tools
    assert ("employer", "retrieve_evidence") in tools
    assert ("registration", "validate_citations") in tools
    sneaky = next(t for t in trace if t["tool_input"].get("query") == "sneaky out of scope")
    assert sneaky["tool_output_summary"].startswith("error:")


def test_unknown_assessment_trace_is_404(client: TestClient) -> None:
    assert client.get("/assessments/nope/trace").status_code == 404


def test_hiring_moves_employer_obligations_to_now(client: TestClient, session: Session, fake: FakeGemini) -> None:
    before = assess_maya(client)
    after = assess_maya(client, session, facts={"has_employees": FactValue(value=True, confirmed=True)})

    assert before["area_scores"]["employer"] is None
    assert after["area_scores"]["employer"] == 0.0
    assert {"EMP-01", "EMP-02", "EMP-03", "EMP-04", "EMP-05"} <= {i["requirement_id"] for i in after["now"]}
    assert {a["agent"]: a["mode"] for a in after["agents"]}["employer"] == "full"


def test_agent_failure_degrades_gracefully(client: TestClient) -> None:
    use_fake(FakeGemini(fail_report_for="tax"))
    body = assess_maya(client)

    tax = {a["agent"]: a for a in body["agents"]}["tax"]
    assert "simulated Gemini outage" in tax["error"]
    findings = {f["requirement_id"]: f for f in body["findings"]}
    assert findings["TAX-01"]["flags"] == [AGENT_UNAVAILABLE_FLAG]
    assert findings["REG-01"]["claims"]  # other agents unaffected
    assert body["cached"] is False  # nothing cached yet for these facts


# --- agent loop -------------------------------------------------------------------------------


async def test_tool_call_cap_is_enforced(maya: BusinessProfile) -> None:
    services = build_stub_services()
    fake = FakeGemini(calls_per_turn=5)
    orchestrator = Orchestrator(services, fake.generate, fake.structured)
    applicability = services.applicability.evaluate(maya)
    agent, scope, mode = orchestrator.plan(maya, applicability)[0]

    output = await agent.run("a-1", maya, scope, mode)

    assert output.tool_calls == agent.max_tool_calls
    executed = [t for t in output.trace if t.tool_name == "get_requirement" and not t.tool_output_summary.startswith("skipped")]
    skipped = [t for t in output.trace if t.tool_output_summary.startswith("skipped")]
    assert len(executed) == agent.max_tool_calls
    assert skipped


def test_employer_mode() -> None:
    def profile(**facts: FactValue) -> BusinessProfile:
        return BusinessProfile(business_id="b", profile_version=1, facts=facts)

    yes, no, unknown = FactValue(value=True, confirmed=True), FactValue(value=False, confirmed=True), FactValue()
    assert employer_mode(profile(has_employees=yes)) == "full"
    assert employer_mode(profile(has_employees=no, plans_to_hire=no)) == "skip"
    assert employer_mode(profile(has_employees=no, plans_to_hire=unknown)) == "pre_hire"
    assert employer_mode(profile()) == "pre_hire"


# --- citation validation ----------------------------------------------------------------------


def _draft(req_id: str, *chunk_lists: list[str]) -> FindingDraft:
    claims = [ClaimDraft(text="c", chunk_ids=ids) for ids in chunk_lists]
    return FindingDraft(requirement_id=req_id, explanation="e", claims=claims, flags=[], confidence=0.9)


def test_claim_with_any_unretrieved_chunk_is_dropped() -> None:
    report = validate_citations([_draft("TAX-01", ["a"], ["a", "b"], [])], ["TAX-01"], {"a"})
    assert [c.chunk_ids for c in report.drafts["TAX-01"].claims] == [["a"]]
    assert report.dropped_claims == 2


def test_finding_without_valid_claims_says_no_source() -> None:
    report = validate_citations([_draft("TAX-01", ["x"])], ["TAX-01", "TAX-02"], {"a"})
    for req_id in ("TAX-01", "TAX-02"):
        draft = report.drafts[req_id]
        assert draft.explanation == NO_SOURCE_EXPLANATION
        assert NO_SOURCE_FLAG in draft.flags
        assert draft.claims == []


def test_out_of_scope_and_duplicate_findings_are_dropped() -> None:
    report = validate_citations(
        [_draft("TAX-01", ["a"]), _draft("TAX-01", ["a"], ["a"]), _draft("EMP-01", ["a"])], ["TAX-01"], {"a"}
    )
    assert list(report.drafts) == ["TAX-01"]
    assert len(report.drafts["TAX-01"].claims) == 1
    assert report.out_of_scope == ["EMP-01"]


# --- requirements route -----------------------------------------------------------------------


def test_requirement_detail(client: TestClient) -> None:
    body = client.get("/requirements/REG-01").json()
    assert body["requirement"]["action_url"] == "TODO-official-url"
    assert body["evidence"]["status"] == "supported"
    assert client.get("/requirements/NOPE-01").status_code == 404
