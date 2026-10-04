"""Updating a profile creates a new version and never mutates the old one."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.contracts.facts import FactValue, RevenueEntry
from app.intake import profile_service
from app.intake.profile_service import ProfileCreate, ProfileUpdate


def test_update_creates_version_2_and_keeps_version_1(session: Session) -> None:
    v1 = profile_service.create_profile(
        session,
        ProfileCreate(
            legal_name="Maya Chen",
            facts={"has_employees": FactValue(value=False, confirmed=True)},
            monthly_revenue=[RevenueEntry(month="2026-09", amount=Decimal("1100"))],
        ),
    )

    v2 = profile_service.update_facts(
        session,
        v1.business_id,
        ProfileUpdate(
            facts={"has_employees": FactValue(value=True, confirmed=True)},
            monthly_revenue=[RevenueEntry(month="2026-10", amount=Decimal("1200"))],
        ),
    )

    assert v1.profile_version == 1
    assert v2.profile_version == 2

    stored_v1 = profile_service.get_version(session, v1.business_id, 1)
    stored_v2 = profile_service.get_latest(session, v1.business_id)
    assert stored_v1 is not None and stored_v2 is not None

    assert stored_v1.facts["has_employees"].value is False
    assert [e.month for e in stored_v1.monthly_revenue] == ["2026-09"]

    assert stored_v2.profile_version == 2
    assert stored_v2.facts["has_employees"].value is True
    assert stored_v2.legal_name == "Maya Chen"
    assert [e.month for e in stored_v2.monthly_revenue] == ["2026-09", "2026-10"]


def test_direct_profile_patch_confirms_raw_frontend_answers_and_versions(client: TestClient) -> None:
    created = client.post(
        "/profile",
        json={"facts": {"has_employees": {"value": False, "confirmed": True}}},
    ).json()
    business_id = created["business_id"]

    response = client.patch(
        f"/profile/{business_id}",
        json={
            "facts": {"plans_to_hire": True, "sells": "goods"},
            "monthly_revenue": [{"month": "2026-10", "amount": 825}],
        },
    )

    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["profile_version"] == 2
    assert updated["facts"]["plans_to_hire"] == {"value": True, "confirmed": True}
    assert updated["facts"]["sells"] == {"value": "goods", "confirmed": True}
    assert updated["monthly_revenue"] == [{"month": "2026-10", "amount": "825"}]

    original = client.get(f"/profile/{business_id}?version=1").json()
    assert original["profile_version"] == 1
    assert "plans_to_hire" not in original["facts"]


def test_direct_profile_patch_rejects_empty_or_invalid_answers(client: TestClient) -> None:
    business_id = client.post("/profile", json={}).json()["business_id"]

    assert client.patch(f"/profile/{business_id}", json={}).status_code == 422
    invalid = client.patch(f"/profile/{business_id}", json={"facts": {"sells": "widgets"}})
    assert invalid.status_code == 422
    assert "expected one of" in invalid.json()["detail"]
    assert client.get(f"/profile/{business_id}").json()["profile_version"] == 1
    assert client.patch("/profile/missing", json={"facts": {"sells": "goods"}}).status_code == 404
