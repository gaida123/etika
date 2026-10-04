"""Stub PST small seller test against the Maya persona."""

from decimal import Decimal

from app.assessment.stubs import StubCalculatorService
from app.contracts.facts import BusinessProfile, FactValue, RevenueEntry


def _with_revenue(profile: BusinessProfile, month: str, extra: Decimal) -> BusinessProfile:
    revenue = [
        RevenueEntry(month=e.month, amount=e.amount + extra if e.month == month else e.amount)
        for e in profile.monthly_revenue
    ]
    return profile.model_copy(update={"monthly_revenue": revenue})


def test_maya_8200_is_exempt(maya: BusinessProfile) -> None:
    result = StubCalculatorService().run("pst_small_seller_test", maya)

    assert result.outcome == "exempt"
    assert result.numbers_used["rolling_12_month_total"] == 8200
    assert result.estimated_crossing is not None


def test_adding_2000_in_one_month_must_register(maya: BusinessProfile) -> None:
    bumped = _with_revenue(maya, "2026-07", Decimal("2000"))
    result = StubCalculatorService().run("pst_small_seller_test", bumped)

    assert result.outcome == "must_register"
    assert result.numbers_used["rolling_12_month_total"] == 10200


def test_missing_revenue_is_undetermined(maya: BusinessProfile) -> None:
    result = StubCalculatorService().run("pst_small_seller_test", maya.model_copy(update={"monthly_revenue": []}))
    assert result.outcome == "undetermined"


def test_unknown_premises_is_undetermined_not_exempt(maya: BusinessProfile) -> None:
    facts = {**maya.facts, "has_established_premises": FactValue(value=None, confirmed=False)}
    result = StubCalculatorService().run("pst_small_seller_test", maya.model_copy(update={"facts": facts}))
    assert result.outcome == "undetermined"
