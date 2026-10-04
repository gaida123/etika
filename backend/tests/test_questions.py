"""Follow-up questions for missing facts."""

from fastapi.testclient import TestClient

from app.contracts.assessment import ApplicabilityResult, ApplicabilityStatus
from app.intake.questions import follow_up_questions

U = ApplicabilityStatus.undetermined


def test_one_question_per_missing_fact_listing_requirements() -> None:
    questions = follow_up_questions(
        [
            ApplicabilityResult(requirement_id="TAX-01", status=U, missing_facts=["sells", "monthly_revenue"]),
            ApplicabilityResult(requirement_id="TAX-02", status=U, missing_facts=["monthly_revenue"]),
        ]
    )
    assert [q.fact_key for q in questions] == ["sells", "monthly_revenue"]
    assert questions[0].options == ["goods", "services", "both"]
    assert questions[1].answer_type == "monthly_revenue"
    assert questions[1].needed_for == ["TAX-01", "TAX-02"]


def test_maya_is_asked_about_hiring_plans(client: TestClient) -> None:
    business_id = client.post("/dev/load-demo").json()["business_id"]
    questions = client.get(f"/profile/{business_id}/questions").json()
    assert [q["fact_key"] for q in questions] == ["plans_to_hire"]
    assert questions[0]["answer_type"] == "bool"


def test_empty_profile_asks_core_questions(client: TestClient) -> None:
    business_id = client.post("/profile", json={}).json()["business_id"]
    keys = [q["fact_key"] for q in client.get(f"/profile/{business_id}/questions").json()]
    assert {"trading_name_differs_from_legal_name", "operates_in_vancouver", "sells", "has_employees"} <= set(keys)
