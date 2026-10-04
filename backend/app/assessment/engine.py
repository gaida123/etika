"""Deterministic Phase 1 applicability, threshold, scoring and sequencing services.

These classes deliberately make no model calls. Regulatory conditions are the
demo-approved rules in the registry and must be re-reviewed before production.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from app.contracts.assessment import (
    STATUS_CREDIT, ApplicabilityResult, ApplicabilityStatus, AssessmentItem,
    AssessmentResult, CalculatorResult, Finding, Flag,
)
from app.contracts.facts import BusinessProfile, RevenueEntry
from app.contracts.registry import Area, Requirement
from app.contracts.services import RegistryService

PST_SMALL_SELLER_THRESHOLD = Decimal("10000")
GST_SMALL_SUPPLIER_THRESHOLD = Decimal("30000")
PROJECTION_HORIZON_MONTHS = 36
AREAS: tuple[Area, ...] = ("registration", "tax", "employer")
EMPLOYER_TRIGGERED = ("EMP-01", "EMP-02", "EMP-03", "EMP-04", "EMP-05")
S = ApplicabilityStatus


def _month_index(month: str) -> int:
    year, mon = month.split("-")
    return int(year) * 12 + int(mon) - 1


def _month_str(index: int) -> str:
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def _revenue_by_month(entries: list[RevenueEntry]) -> dict[int, Decimal]:
    totals: dict[int, Decimal] = defaultdict(Decimal)
    for entry in entries:
        totals[_month_index(entry.month)] += entry.amount
    return dict(totals)


def _rolling_12(values: dict[int, Decimal], end: int) -> Decimal:
    return sum((values.get(month, Decimal(0)) for month in range(end - 11, end + 1)), Decimal(0))


def _project_crossing(values: dict[int, Decimal], threshold: Decimal) -> str | None:
    end = max(values)
    recent = [values.get(month, Decimal(0)) for month in range(end - 5, end + 1)]
    slope = (recent[-1] - recent[0]) / Decimal(len(recent) - 1)
    projected = dict(values)
    for offset in range(1, PROJECTION_HORIZON_MONTHS + 1):
        projected[end + offset] = max(Decimal(0), recent[-1] + slope * offset)
        if _rolling_12(projected, end + offset) > threshold:
            return _month_str(end + offset)
    return None


class DeterministicCalculatorService:
    """PST/GST threshold calculations from confirmed profile revenue only."""

    def run(self, name: str, profile: BusinessProfile) -> CalculatorResult:
        if name == "pst_small_seller_test":
            return self._pst(profile)
        if name == "gst_small_supplier_test":
            return self._gst(profile)
        raise ValueError(f"Unknown calculator: {name}")

    def _pst(self, profile: BusinessProfile) -> CalculatorResult:
        if not profile.monthly_revenue:
            return CalculatorResult(name="pst_small_seller_test", outcome="undetermined", numbers_used={"missing": ["monthly_revenue"]})
        values, end = _revenue_by_month(profile.monthly_revenue), None
        end = max(values)
        total = _rolling_12(values, end)
        premises = profile.fact("has_established_premises")
        numbers = {"window_start": _month_str(end - 11), "window_end": _month_str(end), "rolling_12_month_total": float(total), "threshold": float(PST_SMALL_SELLER_THRESHOLD), "has_established_premises": premises.value if premises.is_known else None}
        if total > PST_SMALL_SELLER_THRESHOLD or (premises.is_known and premises.value is True):
            return CalculatorResult(name="pst_small_seller_test", outcome="must_register", numbers_used=numbers)
        if not premises.is_known:
            numbers["missing"] = ["has_established_premises"]
            return CalculatorResult(name="pst_small_seller_test", outcome="undetermined", numbers_used=numbers)
        return CalculatorResult(name="pst_small_seller_test", outcome="exempt", numbers_used=numbers, estimated_crossing=_project_crossing(values, PST_SMALL_SELLER_THRESHOLD))

    def _gst(self, profile: BusinessProfile) -> CalculatorResult:
        if not profile.monthly_revenue:
            return CalculatorResult(name="gst_small_supplier_test", outcome="undetermined", numbers_used={"missing": ["monthly_revenue"]})
        values = _revenue_by_month(profile.monthly_revenue)
        quarters: dict[int, Decimal] = defaultdict(Decimal)
        for month, amount in values.items():
            quarters[month // 3] += amount
        last = max(quarters)
        four_quarter_total = sum((quarters.get(quarter, Decimal(0)) for quarter in range(last - 3, last + 1)), Decimal(0))
        numbers = {"max_single_quarter": float(max(quarters.values())), "last_four_quarters_total": float(four_quarter_total), "threshold": float(GST_SMALL_SUPPLIER_THRESHOLD)}
        if max(quarters.values()) > GST_SMALL_SUPPLIER_THRESHOLD or four_quarter_total > GST_SMALL_SUPPLIER_THRESHOLD:
            return CalculatorResult(name="gst_small_supplier_test", outcome="must_register", numbers_used=numbers)
        return CalculatorResult(name="gst_small_supplier_test", outcome="exempt", numbers_used=numbers, estimated_crossing=_project_crossing(values, GST_SMALL_SUPPLIER_THRESHOLD))


class DeterministicApplicabilityService:
    """Code-owned applicability for the reviewed demo registry IDs."""

    def __init__(self, registry: RegistryService, calculators: DeterministicCalculatorService) -> None:
        self._registry, self._calculators = registry, calculators

    def evaluate(self, profile: BusinessProfile) -> list[ApplicabilityResult]:
        results: dict[str, ApplicabilityResult] = {}
        def put(identifier: str, status: ApplicabilityStatus, missing: list[str] | None = None) -> None:
            results[identifier] = ApplicabilityResult(requirement_id=identifier, status=status, missing_facts=missing or [])
        def boolean(key: str) -> tuple[ApplicabilityStatus, list[str]]:
            fact = profile.fact(key)
            return (S.undetermined, [key]) if not fact.is_known else (S.required_now if fact.value is True else S.not_applicable, [])

        put("REG-01", *boolean("trading_name_differs_from_legal_name"))
        put("REG-02", *boolean("operates_in_vancouver"))
        sells = profile.fact("sells")
        if not sells.is_known:
            put("TAX-01", S.undetermined, ["sells"])
        elif sells.value == "services":
            put("TAX-01", S.not_applicable)
        else:
            put("TAX-01", *_from_calculator(self._calculators.run("pst_small_seller_test", profile)))
        gst = self._calculators.run("gst_small_supplier_test", profile)
        put("TAX-02", *_from_calculator(gst))
        put("TAX-03", {"exempt": S.upcoming, "must_register": S.not_applicable, "undetermined": S.undetermined}[gst.outcome], list(gst.numbers_used.get("missing", [])))
        put("TAX-04", *_combine([results["TAX-01"], results["TAX-02"]]))
        has_employees, plans_to_hire = profile.fact("has_employees"), profile.fact("plans_to_hire")
        if has_employees.is_known and has_employees.value is True:
            employer, missing = S.required_now, []
        elif not has_employees.is_known:
            employer, missing = S.undetermined, ["has_employees"]
        elif plans_to_hire.is_known and plans_to_hire.value is False:
            employer, missing = S.not_applicable, []
        else:
            employer, missing = S.upcoming, [] if plans_to_hire.is_known else ["plans_to_hire"]
        for identifier in EMPLOYER_TRIGGERED:
            put(identifier, employer, missing)
        put("EMP-06", S.upcoming if employer in (S.required_now, S.upcoming) else employer, missing)
        put("REG-03", *_combine([results["TAX-02"], results["EMP-02"]]))
        return [results[requirement.id] for requirement in self._registry.all() if requirement.id in results]


def _from_calculator(result: CalculatorResult) -> tuple[ApplicabilityStatus, list[str]]:
    return {"must_register": (S.required_now, []), "exempt": (S.upcoming, []), "undetermined": (S.undetermined, list(result.numbers_used.get("missing", [])))}[result.outcome]


def _combine(parents: list[ApplicabilityResult]) -> tuple[ApplicabilityStatus, list[str]]:
    missing = sorted({key for parent in parents for key in parent.missing_facts})
    for status in (S.required_now, S.undetermined, S.upcoming):
        if any(parent.status == status for parent in parents):
            return status, missing if status == S.undetermined else []
    return S.not_applicable, []


class DeterministicScoringService:
    """Score required-now obligations and sequence cards by dependencies/priority."""

    def __init__(self, registry: RegistryService) -> None:
        self._registry = registry

    def score(self, findings: list[Finding], applicability: list[ApplicabilityResult]) -> AssessmentResult:
        finding_by_id = {finding.requirement_id: finding for finding in findings}
        earned: dict[str, float] = defaultdict(float); possible: dict[str, float] = defaultdict(float)
        now: list[AssessmentItem] = []; next_: list[AssessmentItem] = []; later: list[AssessmentItem] = []
        for result in applicability:
            requirement = self._registry.get(result.requirement_id)
            if requirement is None or result.status == S.not_applicable:
                continue
            finding = finding_by_id.get(requirement.id)
            item = AssessmentItem(requirement_id=requirement.id, title=requirement.title, area=requirement.area, priority=requirement.priority, applicability=result.status, status=finding.status if finding else None, explanation=finding.explanation if finding else None, action_url=requirement.action_url, trigger="first_hire" if requirement.id in EMPLOYER_TRIGGERED else requirement.trigger_rule, missing_facts=result.missing_facts)
            if result.status == S.required_now and requirement.requirement_type == "legal_obligation":
                possible[requirement.area] += requirement.weight; earned[requirement.area] += requirement.weight * STATUS_CREDIT.get(finding.status if finding else "", 0.0); now.append(item)
            elif requirement.area == "employer" and result.status == S.upcoming:
                later.append(item)
            else: next_.append(item)
        flags = [Flag(requirement_id=finding.requirement_id, reason=reason) for finding in findings for reason in finding.flags]
        return AssessmentResult(score=_pct(sum(earned.values()), sum(possible.values())), area_scores={area: _pct(earned[area], possible[area]) for area in AREAS}, now=self._sequence(now), next=self._sequence(next_), later=self._sequence(later), flags=flags)

    def _sequence(self, items: list[AssessmentItem]) -> list[AssessmentItem]:
        by_id = {item.requirement_id: item for item in items}
        priority = {"high": 0, "medium": 1, "low": 2}
        return sorted(items, key=lambda item: (sum(1 for dependency in (self._registry.get(item.requirement_id).depends_on if self._registry.get(item.requirement_id) else []) if dependency in by_id), priority[item.priority], item.requirement_id))


def _pct(earned: float, possible: float) -> float | None:
    return round(100 * earned / possible, 1) if possible else None
