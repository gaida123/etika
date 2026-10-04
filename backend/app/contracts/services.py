"""Interfaces for Developer 1's services. Developer 2 codes against these Protocols only.

Stubs live in ``app.knowledge.stubs`` and ``app.assessment.stubs``; real implementations replace
them without changing these signatures.
"""

from collections.abc import Sequence
from typing import Protocol

from app.contracts.assessment import ApplicabilityResult, AssessmentResult, CalculatorResult, Finding
from app.contracts.facts import BusinessProfile
from app.contracts.registry import Area, Requirement
from app.contracts.retrieval import RetrievalRequest, RetrievalResult


class RetrievalService(Protocol):
    """Returns official evidence for a request, or ``insufficient_evidence``."""

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult: ...

    def retrieve_many(self, requests: Sequence[RetrievalRequest]) -> list[RetrievalResult]: ...

    def knowledge_base_version(self) -> str: ...


class RegistryService(Protocol):
    """Read access to the requirement registry."""

    def get(self, requirement_id: str) -> Requirement | None: ...

    def list_by_area(self, area: Area) -> list[Requirement]: ...

    def all(self) -> list[Requirement]: ...


class ApplicabilityService(Protocol):
    """Decides, in code, which requirements apply to a profile."""

    def evaluate(self, profile: BusinessProfile) -> list[ApplicabilityResult]: ...


class CalculatorService(Protocol):
    """Runs a named threshold calculator (e.g. ``pst_small_seller_test``)."""

    def run(self, name: str, profile: BusinessProfile) -> CalculatorResult: ...


class ScoringService(Protocol):
    """Computes the readiness score and now/next/later lists (HANDOFF section 2.5)."""

    def score(
        self, findings: list[Finding], applicability: list[ApplicabilityResult]
    ) -> AssessmentResult: ...
