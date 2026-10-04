"""Stub scoring: only required_now legal obligations count (HANDOFF section 2.5)."""

from app.assessment.stubs import StubScoringService
from app.contracts.assessment import ApplicabilityResult, ApplicabilityStatus, Finding
from app.core.services import build_stub_services
from app.knowledge.stubs import StubRegistryService

S = ApplicabilityStatus


def _finding(req_id: str, status: str) -> Finding:
    return Finding(requirement_id=req_id, status=status, explanation="x", confidence=0.9)  # type: ignore[arg-type]


def _app(req_id: str, status: ApplicabilityStatus) -> ApplicabilityResult:
    return ApplicabilityResult(requirement_id=req_id, status=status)


def test_upcoming_and_recommendations_do_not_change_score() -> None:
    scoring = StubScoringService(StubRegistryService())
    base_app = [_app("REG-01", S.required_now), _app("REG-02", S.required_now)]
    findings = [_finding("REG-01", "done"), _finding("REG-02", "not_done")]

    base = scoring.score(findings, base_app)

    extra_app = base_app + [
        _app("TAX-01", S.upcoming),  # upcoming legal obligation
        _app("EMP-01", S.upcoming),
        _app("TAX-03", S.required_now),  # recommendation, even if marked required_now
        _app("EMP-06", S.required_now),
        _app("TAX-02", S.undetermined),
    ]
    extra_findings = findings + [_finding("TAX-01", "not_done"), _finding("TAX-03", "not_done")]
    with_extras = scoring.score(extra_findings, extra_app)

    # REG-01 high (3 x 1.0) + REG-02 high (3 x 0) = 50%
    assert base.score == 50.0
    assert with_extras.score == base.score
    assert with_extras.area_scores == base.area_scores
    assert with_extras.area_scores["tax"] is None


def test_formula_weights_and_partial_credit() -> None:
    scoring = StubScoringService(StubRegistryService())
    applicability = [_app("EMP-01", S.required_now), _app("EMP-04", S.required_now)]
    findings = [_finding("EMP-01", "in_progress"), _finding("EMP-04", "done")]

    result = scoring.score(findings, applicability)

    # EMP-01 high: 3 x 0.5 = 1.5; EMP-04 medium: 2 x 1.0 = 2 -> 3.5 / 5 = 70%
    assert result.area_scores["employer"] == 70.0
    assert result.score == 70.0


def test_maya_end_to_end_with_stubs(maya) -> None:  # type: ignore[no-untyped-def]
    services = build_stub_services()
    applicability = {a.requirement_id: a for a in services.applicability.evaluate(maya)}

    assert applicability["REG-01"].status == S.required_now
    assert applicability["TAX-01"].status == S.upcoming
    assert applicability["EMP-01"].status == S.upcoming
    assert applicability["EMP-01"].missing_facts == ["plans_to_hire"]

    result = services.scoring.score([], list(applicability.values()))
    assert {i.requirement_id for i in result.now} == {"REG-01", "REG-02"}
    assert result.score == 0.0
