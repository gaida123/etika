"""Assessment fingerprint cache (D2-12). Gemini is faked; no live calls."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agents.cache import profile_fingerprint, with_cache
from app.agents.schemas import AgentRunSummary, AssessmentResponse
from app.contracts.facts import BusinessProfile, FactValue
from tests.fake_gemini import FakeGemini
from tests.test_agents import assess_maya, use_fake


def _response(**overrides: object) -> AssessmentResponse:
    body: dict[str, object] = {
        "assessment_id": "live-1",
        "business_id": "b1",
        "profile_version": 1,
        "score": 0.0,
        "area_scores": {"registration": 0.0, "tax": None, "employer": None},
        "now": [],
        "next": [],
        "later": [],
        "flags": [],
        "findings": [],
        "agents": [AgentRunSummary(agent="registration", mode=None, tool_calls=1, findings=2)],
    }
    body.update(overrides)
    return AssessmentResponse.model_validate(body)


def _failed() -> AssessmentResponse:
    return _response(
        assessment_id="fail-1",
        agents=[AgentRunSummary(agent="tax", mode=None, tool_calls=0, findings=2, error="Gemini 429")],
    )


def test_fingerprint_is_stable_and_ignores_identity(maya: BusinessProfile) -> None:
    other = maya.model_copy(update={"business_id": "other", "profile_version": 9})
    assert profile_fingerprint(maya, True) == profile_fingerprint(other, True)
    assert len(profile_fingerprint(maya, True)) == 64


def test_fingerprint_changes_with_facts_or_stubs(maya: BusinessProfile) -> None:
    hired = maya.model_copy(
        update={"facts": {**maya.facts, "has_employees": FactValue(value=True, confirmed=True)}}
    )
    shuffled = maya.model_copy(update={"jurisdiction_ids": list(reversed(maya.jurisdiction_ids))})
    without_unknown = maya.model_copy(
        update={"facts": {key: fact for key, fact in maya.facts.items() if key != "plans_to_hire"}}
    )

    assert profile_fingerprint(maya, True) != profile_fingerprint(hired, True)
    assert profile_fingerprint(maya, True) != profile_fingerprint(maya, False)
    assert profile_fingerprint(maya, True) == profile_fingerprint(shuffled, True)
    assert profile_fingerprint(maya, True) == profile_fingerprint(without_unknown, True)


def test_successful_result_is_saved_and_served_on_later_failure(session: Session, maya: BusinessProfile) -> None:
    live = with_cache(session, maya, _response(), use_stubs=True)
    assert live.cached is False
    assert live.cached_at is None

    served = with_cache(session, maya, _failed(), use_stubs=True)
    assert served.cached is True
    assert served.cached_at is not None
    assert served.assessment_id == "live-1"
    assert served.business_id == maya.business_id
    assert served.profile_version == maya.profile_version
    assert all(agent.error is None for agent in served.agents)


def test_failure_without_cache_returns_the_live_result(session: Session, maya: BusinessProfile) -> None:
    failed = _failed()
    served = with_cache(session, maya, failed, use_stubs=True)
    assert served.cached is False
    assert served.assessment_id == "fail-1"


def test_cache_is_not_served_for_a_different_fingerprint(session: Session, maya: BusinessProfile) -> None:
    with_cache(session, maya, _response(), use_stubs=True)
    hired = maya.model_copy(
        update={"facts": {**maya.facts, "has_employees": FactValue(value=True, confirmed=True)}}
    )
    served = with_cache(session, hired, _failed(), use_stubs=True)
    assert served.cached is False
    assert served.assessment_id == "fail-1"


def test_successful_rerun_overwrites_the_cached_response(session: Session, maya: BusinessProfile) -> None:
    with_cache(session, maya, _response(assessment_id="old"), use_stubs=True)
    with_cache(session, maya, _response(assessment_id="new"), use_stubs=True)
    served = with_cache(session, maya, _failed(), use_stubs=True)
    assert served.assessment_id == "new"


def test_assess_route_falls_back_to_cache_on_agent_failure(client: TestClient) -> None:
    use_fake(FakeGemini())
    first = assess_maya(client)
    assert first["cached"] is False

    use_fake(FakeGemini(fail_report_for="tax"))
    second_id = client.post("/dev/load-demo").json()["business_id"]
    second = client.post(f"/assess/{second_id}").json()

    assert second["cached"] is True
    assert second["cached_at"]
    assert second["business_id"] == second_id
    assert second["assessment_id"] == first["assessment_id"]
    assert second["score"] == first["score"]
    assert all(agent["error"] is None for agent in second["agents"])
