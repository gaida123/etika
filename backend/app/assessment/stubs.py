"""STUB: replaced by Developer 1.

Minimal applicability rules, threshold calculators and scoring used when ``USE_STUBS=true``.
They satisfy the protocols in ``app.contracts.services``. Rules are hard-coded per requirement ID
instead of interpreting ``applies_if``; thresholds below are draft values pending research review.
"""

from collections import defaultdict
from decimal import Decimal

from app.contracts.assessment import (
    STATUS_CREDIT,
    ApplicabilityResult,
    ApplicabilityStatus,
    AssessmentItem,
    AssessmentResult,
    CalculatorResult,
    Finding,
    Flag,
)
from app.contracts.facts import BusinessProfile, RevenueEntry
from app.contracts.registry import Area, Requirement
from app.knowledge.stubs import StubRegistryService

PST_SMALL_SELLER_THRESHOLD = Decimal("10000")  # STUB: replaced by Developer 1
GST_SMALL_SUPPLIER_THRESHOLD = Decimal("30000")  # STUB: replaced by Developer 1
PROJECTION_HORIZON_MONTHS = 36

AREAS: tuple[Area, ...] = ("registration", "tax", "employer")
EMPLOYER_TRIGGERED = ("EMP-01", "EMP-02", "EMP-03", "EMP-04", "EMP-05")

S = ApplicabilityStatus


# --- month helpers ----------------------------------------------------------------------------


def _month_index(month: str) -> int:
    year, mon = month.split("-")
    return int(year) * 12 + int(mon) - 1


def _month_str(index: int) -> str:
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def _revenue_by_month(entries: list[RevenueEntry]) -> dict[int, Decimal]:
    totals: dict[int, Decimal] = defaultdict(Decimal)
    for e in entries:
        totals[_month_index(e.month)] += e.amount
    return dict(totals)


def _rolling_12(by_month: dict[int, Decimal], end: int) -> Decimal:
    return sum((by_month.get(m, Decimal(0)) for m in range(end - 11, end + 1)), Decimal(0))


def _project_crossing(by_month: dict[int, Decimal], threshold: Decimal) -> str | None:
    """STUB: replaced by Developer 1. Straight-line trend over the last 6 months, rolled forward."""
    end = max(by_month)
    recent = [by_month.get(m, Decimal(0)) for m in range(end - 5, end + 1)]
    slope = (recent[-1] - recent[0]) / Decimal(len(recent) - 1)
    projected = dict(by_month)
    for k in range(1, PROJECTION_HORIZON_MONTHS + 1):
        projected[end + k] = max(Decimal(0), recent[-1] + slope * k)
        if _rolling_12(projected, end + k) > threshold:
            return _month_str(end + k)
    return None


# --- calculators ------------------------------------------------------------------------------


class StubCalculatorService:
    """STUB: replaced by Developer 1. PST small seller and GST small supplier tests.

    The 12-month window ends at the latest revenue month (not today) so the same profile always
    gives the same result.
    """

    def run(self, name: str, profile: BusinessProfile) -> CalculatorResult:
        if name == "pst_small_seller_test":
            return self._pst(profile)
        if name == "gst_small_supplier_test":
            return self._gst(profile)
        raise ValueError(f"Unknown calculator: {name}")

    def _pst(self, profile: BusinessProfile) -> CalculatorResult:
        name = "pst_small_seller_test"
        if not profile.monthly_revenue:
            return CalculatorResult(name=name, outcome="undetermined", numbers_used={"missing": ["monthly_revenue"]})

        by_month = _revenue_by_month(profile.monthly_revenue)
        end = max(by_month)
        total = _rolling_12(by_month, end)
        premises = profile.fact("has_established_premises")
        numbers = {
            "window_start": _month_str(end - 11),
            "window_end": _month_str(end),
            "rolling_12_month_total": float(total),
            "threshold": float(PST_SMALL_SELLER_THRESHOLD),
            "has_established_premises": premises.value if premises.is_known else None,
        }

        if total > PST_SMALL_SELLER_THRESHOLD or (premises.is_known and premises.value is True):
            return CalculatorResult(name=name, outcome="must_register", numbers_used=numbers)
        if not premises.is_known:
            numbers["missing"] = ["has_established_premises"]
            return CalculatorResult(name=name, outcome="undetermined", numbers_used=numbers)
        return CalculatorResult(
            name=name,
            outcome="exempt",
            numbers_used=numbers,
            estimated_crossing=_project_crossing(by_month, PST_SMALL_SELLER_THRESHOLD),
        )

    def _gst(self, profile: BusinessProfile) -> CalculatorResult:
        name = "gst_small_supplier_test"
        if not profile.monthly_revenue:
            return CalculatorResult(name=name, outcome="undetermined", numbers_used={"missing": ["monthly_revenue"]})

        by_month = _revenue_by_month(profile.monthly_revenue)
        quarters: dict[int, Decimal] = defaultdict(Decimal)
        for m, amount in by_month.items():
            quarters[m // 3] += amount
        last_q = max(quarters)
        last_four = sum((quarters.get(q, Decimal(0)) for q in range(last_q - 3, last_q + 1)), Decimal(0))
        max_quarter = max(quarters.values())
        numbers = {
            "max_single_quarter": float(max_quarter),
            "last_four_quarters_total": float(last_four),
            "threshold": float(GST_SMALL_SUPPLIER_THRESHOLD),
        }

        if max_quarter > GST_SMALL_SUPPLIER_THRESHOLD or last_four > GST_SMALL_SUPPLIER_THRESHOLD:
            return CalculatorResult(name=name, outcome="must_register", numbers_used=numbers)
        return CalculatorResult(
            name=name,
            outcome="exempt",
            numbers_used=numbers,
            estimated_crossing=_project_crossing(by_month, GST_SMALL_SUPPLIER_THRESHOLD),
        )


# --- applicability ----------------------------------------------------------------------------


def _bool_rule(profile: BusinessProfile, key: str) -> ApplicabilityStatus:
    fact = profile.fact(key)
    if not fact.is_known:
        return S.undetermined
    return S.required_now if fact.value is True else S.not_applicable


class StubApplicabilityService:
    """STUB: replaced by Developer 1. Hard-coded rules; unknown facts give ``undetermined``."""

    def __init__(self, registry: StubRegistryService, calculators: StubCalculatorService) -> None:
        self._registry = registry
        self._calculators = calculators

    def evaluate(self, profile: BusinessProfile) -> list[ApplicabilityResult]:
        r: dict[str, ApplicabilityResult] = {}

        def put(req_id: str, status: ApplicabilityStatus, missing: list[str] | None = None) -> None:
            r[req_id] = ApplicabilityResult(requirement_id=req_id, status=status, missing_facts=missing or [])

        # Registration
        status = _bool_rule(profile, "trading_name_differs_from_legal_name")
        put("REG-01", status, ["trading_name_differs_from_legal_name"] if status == S.undetermined else None)
        status = _bool_rule(profile, "operates_in_vancouver")
        put("REG-02", status, ["operates_in_vancouver"] if status == S.undetermined else None)

        # Tax
        sells = profile.fact("sells")
        if not sells.is_known:
            put("TAX-01", S.undetermined, ["sells"])
        elif sells.value == "services":
            put("TAX-01", S.not_applicable)
        else:
            put("TAX-01", *_from_calculator(self._calculators.run("pst_small_seller_test", profile)))

        gst = self._calculators.run("gst_small_supplier_test", profile)
        put("TAX-02", *_from_calculator(gst))
        tax03 = {"exempt": S.upcoming, "must_register": S.not_applicable, "undetermined": S.undetermined}
        put("TAX-03", tax03[gst.outcome], gst.numbers_used.get("missing"))
        put("TAX-04", *_combine([r["TAX-01"], r["TAX-02"]]))

        # Employer
        has_emp, plans = profile.fact("has_employees"), profile.fact("plans_to_hire")
        if has_emp.is_known and has_emp.value is True:
            emp, emp_missing = S.required_now, []
        elif not has_emp.is_known:
            emp, emp_missing = S.undetermined, ["has_employees"]
        elif plans.is_known and plans.value is False:
            emp, emp_missing = S.not_applicable, []
        else:
            emp, emp_missing = S.upcoming, [] if plans.is_known else ["plans_to_hire"]
        for req_id in EMPLOYER_TRIGGERED:
            put(req_id, emp, emp_missing)
        put("EMP-06", S.upcoming if emp in (S.required_now, S.upcoming) else emp, emp_missing)

        # Business number is needed once GST or payroll is
        put("REG-03", *_combine([r["TAX-02"], r["EMP-02"]]))

        return [r[req.id] for req in self._registry.all() if req.id in r]


def _from_calculator(result: CalculatorResult) -> tuple[ApplicabilityStatus, list[str]]:
    mapping = {"must_register": S.required_now, "exempt": S.upcoming, "undetermined": S.undetermined}
    return mapping[result.outcome], list(result.numbers_used.get("missing", []))


def _combine(parents: list[ApplicabilityResult]) -> tuple[ApplicabilityStatus, list[str]]:
    """Strongest status among parents: required_now > undetermined > upcoming > not_applicable."""
    missing = sorted({f for p in parents for f in p.missing_facts})
    for status in (S.required_now, S.undetermined, S.upcoming):
        if any(p.status == status for p in parents):
            return status, missing if status == S.undetermined else []
    return S.not_applicable, []


# --- scoring ----------------------------------------------------------------------------------


class StubScoringService:
    """STUB: replaced by Developer 1. Implements HANDOFF section 2.5.

    Only ``required_now`` legal obligations count. Weight high=3, medium=2, low=1; credit
    done=1.0, in_progress=0.5, anything else (or no finding)=0. Area/overall score is ``None``
    when nothing is required.
    """

    def __init__(self, registry: StubRegistryService) -> None:
        self._registry = registry

    def score(self, findings: list[Finding], applicability: list[ApplicabilityResult]) -> AssessmentResult:
        by_req = {f.requirement_id: f for f in findings}
        earned: dict[str, float] = defaultdict(float)
        possible: dict[str, float] = defaultdict(float)
        now: list[AssessmentItem] = []
        next_: list[AssessmentItem] = []
        later: list[AssessmentItem] = []

        for a in applicability:
            req = self._registry.get(a.requirement_id)
            if req is None or a.status == S.not_applicable:
                continue
            finding = by_req.get(req.id)
            item = _item(req, a, finding)

            if a.status == S.required_now and req.requirement_type == "legal_obligation":
                possible[req.area] += req.weight
                earned[req.area] += req.weight * STATUS_CREDIT.get(finding.status if finding else "", 0.0)
                now.append(item)
            elif req.area == "employer" and a.status == S.upcoming:
                later.append(item)
            else:
                next_.append(item)

        area_scores = {area: _pct(earned[area], possible[area]) for area in AREAS}
        overall = _pct(sum(earned.values()), sum(possible.values()))
        flags = [Flag(requirement_id=f.requirement_id, reason=reason) for f in findings for reason in f.flags]
        return AssessmentResult(score=overall, area_scores=area_scores, now=now, next=next_, later=later, flags=flags)


def _pct(earned: float, possible: float) -> float | None:
    return round(100 * earned / possible, 1) if possible else None


def _item(req: Requirement, a: ApplicabilityResult, finding: Finding | None) -> AssessmentItem:
    return AssessmentItem(
        requirement_id=req.id,
        title=req.title,
        area=req.area,
        priority=req.priority,
        applicability=a.status,
        status=finding.status if finding else None,
        explanation=finding.explanation if finding else None,
        action_url=req.action_url,
        trigger="first_hire" if req.id in EMPLOYER_TRIGGERED else req.trigger_rule,
        missing_facts=a.missing_facts,
    )
