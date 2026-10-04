"""Unknown is never false: unknown facts round-trip as unknown."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.contracts.facts import FactValue
from app.intake import profile_service
from app.intake.profile_service import ProfileCreate


def test_unknown_fact_round_trips_through_db(session: Session) -> None:
    created = profile_service.create_profile(
        session,
        ProfileCreate(facts={"plans_to_hire": FactValue(value=None, confirmed=False)}),
    )
    loaded = profile_service.get_latest(session, created.business_id)

    assert loaded is not None
    fact = loaded.facts["plans_to_hire"]
    assert fact.value is None
    assert fact.value is not False
    assert fact.confirmed is False
    assert not fact.is_known


def test_missing_fact_is_unknown_not_false(session: Session) -> None:
    created = profile_service.create_profile(session, ProfileCreate())
    loaded = profile_service.get_latest(session, created.business_id)

    assert loaded is not None
    assert loaded.fact("has_employees") == FactValue(value=None, confirmed=False)


def test_unconfirmed_value_is_not_known(session: Session) -> None:
    created = profile_service.create_profile(
        session, ProfileCreate(facts={"has_employees": FactValue(value=False, confirmed=False)})
    )
    loaded = profile_service.get_latest(session, created.business_id)

    assert loaded is not None
    assert loaded.facts["has_employees"].confirmed is False
    assert not loaded.facts["has_employees"].is_known


def test_api_returns_unknown_as_null(client: TestClient) -> None:
    resp = client.post("/profile", json={"facts": {"plans_to_hire": {"value": None, "confirmed": False}}})
    assert resp.status_code == 201
    business_id = resp.json()["business_id"]

    body = client.get(f"/profile/{business_id}").json()
    assert body["facts"]["plans_to_hire"] == {"value": None, "confirmed": False}


def test_load_demo_keeps_maya_plans_to_hire_unknown(client: TestClient) -> None:
    body = client.post("/dev/load-demo").json()
    assert body["legal_name"] == "Maya Chen"
    assert body["facts"]["plans_to_hire"] == {"value": None, "confirmed": False}
    assert sum(float(e["amount"]) for e in body["monthly_revenue"]) == 8200
