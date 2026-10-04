"""Phase 2: prefetch + single-call agents. Gemini and retrieval are faked; no live calls."""

import asyncio
from collections.abc import Callable, Iterator, Sequence
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from google.genai import errors

from app.agents.base import ESCALATION_TOOL_CALLS, UNKNOWN_FACT, BaseAgent
from app.agents.orchestrator import Orchestrator
from app.agents.retrieval_adapter import STUB_KB_VERSION, kb_version
from app.agents.schemas import AgentReport, AgentRunOutput, FindingDraft
from app.agents.tools import CALCULATOR_NAMES, AgentToolbox
from app.contracts.assessment import ApplicabilityResult
from app.contracts.facts import BusinessProfile
from app.contracts.retrieval import RetrievalRequest, RetrievalResult
from app.core.services import Services, build_stub_services
from tests.fake_gemini import INVENTED_CHUNK, FakeGemini
from tests.test_agents import assess_maya, use_fake

PREFETCH_TOOLS = {"get_requirement", "retrieve_evidence", "get_profile_fact"}


@pytest.fixture
def prefetch_mode(agent_mode: Callable[..., None]) -> None:
    agent_mode("prefetch")


@pytest.fixture
def fake(client: TestClient) -> Iterator[FakeGemini]:
    fake = FakeGemini()
    use_fake(fake)
    yield fake


def plan_for(
    services: Services, fake: FakeGemini, profile: BusinessProfile, agent_name: str
) -> tuple[BaseAgent, list[ApplicabilityResult], str | None]:
    """The planned (agent, scope, mode) tuple for one agent, exactly as the orchestrator builds it."""
    orchestrator = Orchestrator(services, fake.generate, fake.structured)
    applicability = services.applicability.evaluate(profile)
    return next(p for p in orchestrator.plan(profile, applicability) if p[0].name == agent_name)


def prefetch_entries(output: AgentRunOutput) -> list:
    return [t for t in output.trace if t.tool_input.get("source") == "prefetch"]


class SlowReportFake(FakeGemini):
    """Yields during a report so concurrent report calls are observable in a route test."""

    def __init__(self) -> None:
        super().__init__()
        self.active_reports = 0
        self.max_concurrent_reports = 0

    async def structured(self, prompt: str, system: str, schema: Any) -> Any:
        if schema is not AgentReport:
            return await super().structured(prompt, system, schema)
        self.active_reports += 1
        self.max_concurrent_reports = max(self.max_concurrent_reports, self.active_reports)
        try:
            await asyncio.sleep(0.01)
            return await super().structured(prompt, system, schema)
        finally:
            self.active_reports -= 1


class CountingRetrieval:
    """Wraps the stub service and counts calls. ``batched`` adds Developer 1's Phase 1 interface."""

    def __init__(self, inner: Any, batched: bool) -> None:
        self._inner = inner
        self.singles: list[RetrievalRequest] = []
        self.batches: list[list[RetrievalRequest]] = []
        if batched:
            self.retrieve_many = self._retrieve_many  # type: ignore[method-assign]

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        self.singles.append(request)
        return self._inner.retrieve(request)

    def _retrieve_many(self, requests: Sequence[RetrievalRequest]) -> list[RetrievalResult]:
        self.batches.append(list(requests))
        return [self._inner.retrieve(request) for request in requests]

    def knowledge_base_version(self) -> str:
        return "kb-test-1"


def counting_services(batched: bool) -> tuple[Services, CountingRetrieval]:
    services = build_stub_services()
    retrieval = CountingRetrieval(services.retrieval, batched)
    return replace(services, retrieval=retrieval), retrieval


async def prefetch_with(services: Services, profile: BusinessProfile, agent_name: str) -> AgentRunOutput:
    agent, scope, mode = plan_for(services, FakeGemini(), profile, agent_name)
    output = AgentRunOutput(agent=agent.name, mode=mode, scope=scope)
    toolbox = AgentToolbox(agent.name, "a-batch", profile, services, output, agent.tool_names)
    await agent.prefetch(toolbox, profile, scope, mode)
    return output


# --- prefetch ---------------------------------------------------------------------------------


async def test_prefetch_makes_no_llm_calls(maya: BusinessProfile) -> None:
    services = build_stub_services()
    fake = FakeGemini()
    agent, scope, mode = plan_for(services, fake, maya, "tax")
    output = AgentRunOutput(agent=agent.name, mode=mode, scope=scope)
    toolbox = AgentToolbox(agent.name, "a-1", maya, services, output, agent.tool_names)

    pack = await agent.prefetch(toolbox, maya, scope, mode)

    assert fake.requests == 0
    assert output.tool_calls == 0  # prefetch is code, not a tool loop
    assert [r.requirement_id for r in pack.requirements] == [a.requirement_id for a in scope]
    assert pack.chunk_count > 0
    assert set(pack.calculators) == set(CALCULATOR_NAMES)

    entries = prefetch_entries(output)
    assert PREFETCH_TOOLS | {"get_calculator_result"} <= {t.tool_name for t in entries}
    assert len(entries) == len([t for t in output.trace if t.tool_name in PREFETCH_TOOLS]) + 3

    for req in pack.requirements:
        # only chunks registered as retrieved in this run are citable
        assert req.chunks, req.requirement_id
        for chunk in req.chunks:
            assert chunk.id in output.retrieved
            assert chunk.id in output.evidence_by_requirement[req.requirement_id]
            assert chunk.requirement_id == req.requirement_id


async def test_prefetch_caps_chunks_and_reads_facts_once(maya: BusinessProfile) -> None:
    services = build_stub_services()
    fake = FakeGemini()
    agent, scope, mode = plan_for(services, fake, maya, "employer")
    output = AgentRunOutput(agent=agent.name, mode=mode, scope=scope)
    toolbox = AgentToolbox(agent.name, "a-2", maya, services, output, agent.tool_names)

    pack = await agent.prefetch(toolbox, maya, scope, mode)

    assert all(len(r.chunks) <= 6 for r in pack.requirements)
    fact_entries = [t for t in prefetch_entries(output) if t.tool_name == "get_profile_fact"]
    assert [t.tool_input["key"] for t in fact_entries] == ["has_employees", "plans_to_hire"]


# --- batched retrieval ------------------------------------------------------------------------


async def test_prefetch_batches_the_whole_scope(maya: BusinessProfile) -> None:
    services, retrieval = counting_services(batched=True)
    output = await prefetch_with(services, maya, "registration")

    assert len(retrieval.batches) == 1  # one service call for every (requirement, query) pair
    assert retrieval.singles == []
    batch = retrieval.batches[0]
    entries = [t for t in prefetch_entries(output) if t.tool_name == "retrieve_evidence"]
    assert len(entries) == len(batch)  # one trace entry per pair, in request order
    assert [(t.tool_input["requirement_id"], t.tool_input["query"]) for t in entries] == [
        (r.requirement_ids[0], r.query) for r in batch
    ]
    for request in batch:  # the filters that keep evidence safe to cite survive batching
        assert request.jurisdiction_ids == maya.jurisdiction_ids
        assert request.segment_id == maya.segment_id
        assert request.area == "registration"
        assert request.limit == 3


async def test_sequential_fallback_matches_the_batched_result(maya: BusinessProfile) -> None:
    batched_services, batched = counting_services(batched=True)
    fallback_services, fallback = counting_services(batched=False)

    batched_output = await prefetch_with(batched_services, maya, "tax")
    fallback_output = await prefetch_with(fallback_services, maya, "tax")

    assert len(fallback.singles) == len(batched.batches[0])  # one retrieve per pair, no batching
    assert fallback.batches == []
    assert fallback_output.evidence_by_requirement == batched_output.evidence_by_requirement
    assert fallback_output.retrieved.keys() == batched_output.retrieved.keys()


def test_out_of_scope_pair_does_not_reach_the_service(maya: BusinessProfile) -> None:
    services, retrieval = counting_services(batched=True)
    agent, scope, mode = plan_for(services, FakeGemini(), maya, "tax")
    output = AgentRunOutput(agent=agent.name, mode=mode, scope=scope)
    toolbox = AgentToolbox(agent.name, "a-scope", maya, services, output, agent.tool_names)

    in_scope = scope[0].requirement_id
    results = toolbox.retrieve_evidence_many([("REG-01", "q"), (in_scope, "q")])

    assert "not in your scope" in results[0]["error"]
    assert results[1]["status"] == "supported"
    assert [r.requirement_ids[0] for r in retrieval.batches[0]] == [in_scope]
    assert [t.tool_input["requirement_id"] for t in output.trace] == ["REG-01", in_scope]
    assert "REG-01" not in output.evidence_by_requirement


def test_kb_version_prefers_the_service() -> None:
    assert kb_version(CountingRetrieval(None, batched=True)) == "kb-test-1"
    assert kb_version(build_stub_services().retrieval) == STUB_KB_VERSION


# --- the call budget --------------------------------------------------------------------------


def test_first_run_three_calls(client: TestClient, fake: FakeGemini, prefetch_mode: None) -> None:
    body = assess_maya(client)

    assert fake.requests == 3  # one report call per agent, no tool loop
    assert fake.reports == {"registration": 1, "tax": 1, "employer": 1}
    assert len(body["findings"]) == 13
    assert all(a["error"] is None for a in body["agents"])
    assert all(a["tool_calls"] == 0 for a in body["agents"])


def test_report_calls_are_serialized_per_assessment(client: TestClient, prefetch_mode: None) -> None:
    fake = SlowReportFake()
    use_fake(fake)

    body = assess_maya(client)

    assert all(a["error"] is None for a in body["agents"])
    assert fake.reports == {"registration": 1, "tax": 1, "employer": 1}
    assert fake.max_concurrent_reports == 1


def test_employer_mode_instructions_survive(
    client: TestClient, fake: FakeGemini, prefetch_mode: None
) -> None:
    assess_maya(client)
    employer = next(p for p in fake.report_prompts if "EMP-01" in p)
    assert "Mode: pre_hire" in employer
    assert "day they hire their first employee" in employer


def test_trace_shows_prefetch_steps(client: TestClient, fake: FakeGemini, prefetch_mode: None) -> None:
    body = assess_maya(client)
    trace = client.get(f"/assessments/{body['assessment_id']}/trace").json()

    prefetched = [t for t in trace if t["tool_input"].get("source") == "prefetch"]
    assert PREFETCH_TOOLS <= {t["tool_name"] for t in prefetched}
    assert {t["agent"] for t in prefetched} == {"registration", "tax", "employer"}
    assert ("tax", "get_calculator_result") in [(t["agent"], t["tool_name"]) for t in prefetched]
    assert ("registration", "validate_citations") in [(t["agent"], t["tool_name"]) for t in trace]


# --- citations --------------------------------------------------------------------------------


def test_citations_unchanged(
    client: TestClient, fake: FakeGemini, agent_mode: Callable[..., None]
) -> None:
    agent_mode("legacy")
    legacy = assess_maya(client)
    agent_mode("prefetch")
    prefetch = assess_maya(client)

    def claims(body: dict) -> dict[str, int]:
        return {f["requirement_id"]: len(f["claims"]) for f in body["findings"]}

    legacy_claims, prefetch_claims = claims(legacy), claims(prefetch)
    assert set(prefetch_claims) == set(legacy_claims)
    for req_id, count in legacy_claims.items():
        assert prefetch_claims[req_id] >= count, req_id
    for finding in prefetch["findings"]:
        for claim in finding["claims"]:
            assert claim["chunk_ids"] and INVENTED_CHUNK not in claim["chunk_ids"]


# --- escalation -------------------------------------------------------------------------------


def test_escalation_bounded(client: TestClient, prefetch_mode: None) -> None:
    fake = FakeGemini(low_confidence_for="registration")
    use_fake(fake)

    body = assess_maya(client)
    trace = client.get(f"/assessments/{body['assessment_id']}/trace").json()

    # exactly one extra round for the weak agent: 1 report + investigate + 1 re-report
    assert fake.reports == {"registration": 2, "tax": 1, "employer": 1}
    escalations = [t for t in trace if t["tool_input"].get("escalated")]
    assert len(escalations) == 1
    assert escalations[0]["agent"] == "registration"
    assert sorted(escalations[0]["tool_input"]["requirement_ids"]) == ["REG-01", "REG-02", "REG-03"]

    registration = {a["agent"]: a for a in body["agents"]}["registration"]
    assert registration["tool_calls"] == ESCALATION_TOOL_CALLS
    assert registration["error"] is None


def test_escalation_skipped_when_findings_are_strong(
    client: TestClient, fake: FakeGemini, prefetch_mode: None
) -> None:
    body = assess_maya(client)
    trace = client.get(f"/assessments/{body['assessment_id']}/trace").json()
    assert [t for t in trace if t["tool_input"].get("escalated")] == []


def test_escalation_failure_keeps_original_drafts(
    client: TestClient, prefetch_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeGemini(low_confidence_for="registration")
    use_fake(fake)

    async def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("investigate exploded")

    monkeypatch.setattr(BaseAgent, "investigate", boom)
    body = assess_maya(client)

    registration = {a["agent"]: a for a in body["agents"]}["registration"]
    assert registration["error"] is None  # escalation is best-effort
    findings = {f["requirement_id"]: f for f in body["findings"]}
    assert findings["REG-01"]["claims"]
    trace = client.get(f"/assessments/{body['assessment_id']}/trace").json()
    failed = next(t for t in trace if t["tool_name"] == "escalate")
    assert "escalation failed" in failed["tool_output_summary"]


# --- failure isolation ------------------------------------------------------------------------


def test_agent_error_isolated(client: TestClient, prefetch_mode: None) -> None:
    rate_limited = errors.ClientError(429, {"error": {"status": "RESOURCE_EXHAUSTED"}})
    use_fake(FakeGemini(fail_report_for="tax", report_error=rate_limited))

    body = assess_maya(client)

    agents = {a["agent"]: a for a in body["agents"]}
    assert "429" in (agents["tax"]["error"] or "")
    assert agents["registration"]["error"] is None and agents["employer"]["error"] is None
    findings = {f["requirement_id"]: f for f in body["findings"]}
    assert findings["REG-01"]["claims"] and findings["EMP-01"]["claims"]
    assert findings["TAX-01"]["claims"] == []


# --- code decides, Gemini explains ------------------------------------------------------------


def test_status_not_from_gemini(client: TestClient, prefetch_mode: None) -> None:
    use_fake(FakeGemini(inject_status=True))
    assert "status" not in FindingDraft.model_fields  # the schema has no status field

    body = assess_maya(client)

    findings = {f["requirement_id"]: f for f in body["findings"]}
    assert findings["REG-01"]["status"] == "not_done"  # required_now
    assert findings["TAX-01"]["status"] == "not_yet_required"  # upcoming
    assert "done" not in [f["status"] for f in body["findings"]]


def test_unknown_fact_preserved(client: TestClient, fake: FakeGemini, prefetch_mode: None) -> None:
    assess_maya(client)

    prompt = next(p for p in fake.report_prompts if "plans_to_hire" in p)
    for line in prompt.splitlines():
        if line.startswith("- plans_to_hire:"):
            assert line.endswith(UNKNOWN_FACT) or line.endswith("unknown")
    assert f"- plans_to_hire: {UNKNOWN_FACT}" in prompt
    assert "- plans_to_hire: False" not in prompt
    assert "- has_employees: False" in prompt  # a confirmed false fact still reads as false


# --- the feature flag -------------------------------------------------------------------------


def test_legacy_mode_unchanged(client: TestClient, fake: FakeGemini, agent_mode: Callable[..., None]) -> None:
    agent_mode("legacy")
    body = assess_maya(client)
    trace = client.get(f"/assessments/{body['assessment_id']}/trace").json()

    assert fake.requests > 3  # tool loop plus a report call per agent
    assert len(body["findings"]) == 13
    assert [t for t in trace if t["tool_input"].get("source") == "prefetch"] == []
    assert any(a["tool_calls"] > 0 for a in body["agents"])
