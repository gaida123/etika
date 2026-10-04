"""Phase 1 real registry/engine checks without a live TiDB connection."""

from pathlib import Path

from sqlalchemy.orm import Session

from app.api.routes_dev import load_maya_fixture
from app.assessment.engine import (
    DeterministicApplicabilityService,
    DeterministicCalculatorService,
    DeterministicScoringService,
)
from app.contracts.assessment import Finding
from app.contracts.facts import BusinessProfile
from app.core.db import Base, make_engine
from app.knowledge.tidb_registry import TiDBRegistryService, load_registry_file, upsert_requirements


def _registry() -> TiDBRegistryService:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    path = Path(__file__).resolve().parents[1] / "data" / "registry" / "requirements.json"
    with Session(engine) as session:
        upsert_requirements(session, load_registry_file(str(path)))
        session.commit()
    return TiDBRegistryService(engine, allow_drafts=True)


def test_registry_loader_hides_placeholder_action_urls() -> None:
    registry = _registry()

    assert len(registry.all()) == 13
    assert registry.get("REG-01") is not None
    assert registry.get("REG-01").action_url is None  # type: ignore[union-attr]


def test_real_engine_evaluates_and_sequences_demo_profile() -> None:
    registry = _registry()
    profile = BusinessProfile(business_id="maya", profile_version=1, **load_maya_fixture().model_dump())
    calculators = DeterministicCalculatorService()
    applicability = DeterministicApplicabilityService(registry, calculators).evaluate(profile)

    by_id = {result.requirement_id: result.status.value for result in applicability}
    assert by_id["REG-01"] == "required_now"
    assert by_id["TAX-01"] == "upcoming"
    assert by_id["EMP-01"] == "upcoming"

    result = DeterministicScoringService(registry).score(
        [Finding(requirement_id="REG-01", status="done", explanation="done", confidence=1)], applicability
    )
    assert result.score == 50.0
    assert [item.requirement_id for item in result.now] == ["REG-01", "REG-02"]
