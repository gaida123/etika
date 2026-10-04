"""Assessment contracts: applicability, calculators, agent findings and the scored result.

Code (Developer 1) decides applicability, thresholds and the score. Agents (Developer 2) only
explain, cite and flag via ``Finding``.
"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.contracts.registry import Area, Priority

FindingStatus = Literal["done", "in_progress", "not_done", "not_yet_required", "undetermined"]

STATUS_CREDIT: dict[str, float] = {"done": 1.0, "in_progress": 0.5, "not_done": 0.0}


class ApplicabilityStatus(str, Enum):
    """Whether a requirement applies to the profile, as decided by code."""

    required_now = "required_now"
    upcoming = "upcoming"
    not_applicable = "not_applicable"
    undetermined = "undetermined"


class ApplicabilityResult(BaseModel):
    """Applicability of one requirement; ``missing_facts`` become follow-up questions."""

    requirement_id: str
    status: ApplicabilityStatus
    missing_facts: list[str] = Field(default_factory=list)


class CalculatorResult(BaseModel):
    """Output of a deterministic threshold calculator (e.g. ``pst_small_seller_test``)."""

    name: str
    outcome: Literal["exempt", "must_register", "undetermined"]
    numbers_used: dict[str, Any] = Field(default_factory=dict)
    estimated_crossing: str | None = Field(
        default=None, description="Projected month (YYYY-MM) the threshold is crossed. Always an estimate."
    )


class Claim(BaseModel):
    """One compliance statement plus the chunk IDs (retrieved in the same run) that support it."""

    text: str
    chunk_ids: list[str] = Field(min_length=1)


class Finding(BaseModel):
    """An agent's explanation of one requirement (HANDOFF section 5.5)."""

    requirement_id: str
    status: FindingStatus
    explanation: str = Field(description="Plain English, for the owner.")
    claims: list[Claim] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list, description="Gray areas sent for review.")
    confidence: float = Field(ge=0.0, le=1.0, description="Below ~0.6 means 'check with a professional'.")


class Flag(BaseModel):
    """A gray area raised for human review; never a conclusion."""

    requirement_id: str
    reason: str


class SourceLink(BaseModel):
    """A cited official source shown on a card."""

    title: str
    url: str


class AssessmentItem(BaseModel):
    """One dashboard card in the now / next / later lists (HANDOFF section 8.3)."""

    requirement_id: str
    title: str
    area: Area
    priority: Priority
    applicability: ApplicabilityStatus
    status: FindingStatus | None = None
    explanation: str | None = None
    action_url: str | None = None
    sources: list[SourceLink] = Field(default_factory=list)
    progress: dict[str, Any] | None = Field(
        default=None, examples=[{"current": 8200, "threshold": 10000, "estimated_crossing": "2027-03"}]
    )
    trigger: str | None = Field(default=None, examples=["first_hire"])
    missing_facts: list[str] = Field(default_factory=list)


class AssessmentResult(BaseModel):
    """Scored output of one assessment run.

    Only ``required_now`` legal obligations count toward ``score``; ``None`` means nothing is
    required yet in that scope.
    """

    score: float | None
    area_scores: dict[Area, float | None]
    now: list[AssessmentItem] = Field(default_factory=list)
    next: list[AssessmentItem] = Field(default_factory=list)
    later: list[AssessmentItem] = Field(default_factory=list)
    flags: list[Flag] = Field(default_factory=list)
