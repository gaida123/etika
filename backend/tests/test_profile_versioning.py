"""Updating a profile creates a new version and never mutates the old one."""

from decimal import Decimal

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
