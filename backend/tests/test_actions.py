"""Owner-controlled inquiry drafts: deterministic, unsent, and registry-bound."""

from fastapi.testclient import TestClient

from app.actions.inquiry_draft import build_inquiry_draft
from app.contracts.facts import BusinessProfile, FactValue
from app.contracts.registry import Requirement


def test_draft_email_uses_confirmed_profile_context_and_hides_placeholder_link(client: TestClient) -> None:
    profile = client.post(
        "/profile",
        json={
            "trading_name": "Wick & Co",
            "facts": {
                "operates_in_vancouver": {"value": True, "confirmed": True},
                "home_based": {"value": True, "confirmed": True},
                "online_only": {"value": False, "confirmed": True},
                "trading_name_differs_from_legal_name": {"value": True, "confirmed": True},
            },
        },
    ).json()

    response = client.post(
        "/draft-email",
        json={"business_id": profile["business_id"], "requirement_id": "REG-01"},
    )

    assert response.status_code == 200, response.text
    draft = response.json()
    assert draft["profile_version"] == 1
    assert draft["requirement_id"] == "REG-01"
    assert draft["recipient_hint"] == "The relevant registration or licensing authority"
    assert "Wick & Co" in draft["body"]
    assert "Operates in the City of Vancouver: Yes" in draft["body"]
    assert "Could you please confirm whether this requirement applies" in draft["body"]
    assert draft["action_url"] is None  # Stub registry's TODO link is never exposed.
    assert "TODO" not in draft["body"]
    assert "$" not in draft["body"]
    assert "does not send email" in draft["disclaimer"]


def test_draft_email_returns_404_for_missing_profile_or_requirement(client: TestClient) -> None:
    assert client.post("/draft-email", json={"business_id": "missing", "requirement_id": "REG-01"}).status_code == 404

    business_id = client.post("/profile", json={}).json()["business_id"]
    assert client.post("/draft-email", json={"business_id": business_id, "requirement_id": "NOPE-01"}).status_code == 404


def test_inquiry_draft_only_forwards_concrete_registry_http_url() -> None:
    profile = BusinessProfile(
        business_id="b-1",
        profile_version=1,
        facts={"has_employees": FactValue(value=True, confirmed=True)},
    )
    requirement = Requirement(
        id="EMP-01",
        area="employer",
        title="Register with WorkSafeBC",
        requirement_type="legal_obligation",
        timing="trigger",
        priority="high",
        action_url="https://www.worksafebc.com/en/insurance/apply-for-coverage",
    )

    draft = build_inquiry_draft(profile, requirement)

    assert draft.action_url == requirement.action_url
    assert requirement.action_url not in draft.body
