"""Service factory: returns Developer 1's stubs or real implementations based on USE_STUBS."""

from dataclasses import dataclass
from functools import lru_cache

from app.contracts.services import (
    ApplicabilityService,
    CalculatorService,
    RegistryService,
    RetrievalService,
    ScoringService,
)
from app.core.settings import get_settings


@dataclass(frozen=True)
class Services:
    """Bundle of Developer 1's services, typed by their Protocols."""

    registry: RegistryService
    retrieval: RetrievalService
    applicability: ApplicabilityService
    calculators: CalculatorService
    scoring: ScoringService


def build_stub_services() -> Services:
    """STUB: replaced by Developer 1. Wire the in-memory stub services together."""
    from app.assessment.stubs import (
        StubApplicabilityService,
        StubCalculatorService,
        StubScoringService,
    )
    from app.knowledge.stubs import StubRegistryService, StubRetrievalService

    registry = StubRegistryService()
    calculators = StubCalculatorService()
    return Services(
        registry=registry,
        retrieval=StubRetrievalService(),
        applicability=StubApplicabilityService(registry, calculators),
        calculators=calculators,
        scoring=StubScoringService(registry),
    )


def build_real_services() -> Services:
    """Developer 1 wires the TiDB-backed implementations here."""
    raise NotImplementedError(
        "Real services are not wired yet (Developer 1). Set USE_STUBS=true for now."
    )


@lru_cache
def get_services() -> Services:
    """Return stubs when USE_STUBS=true, otherwise the real implementations."""
    return build_stub_services() if get_settings().use_stubs else build_real_services()
