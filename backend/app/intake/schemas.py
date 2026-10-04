"""Intake request/response models (Developer 2; consumed by the front end)."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.contracts.facts import BusinessProfile
from app.intake.fact_dictionary import FactKey


class ExtractedFact(BaseModel):
    """One fact as returned by Gemini. ``value`` is a string; code parses and validates it."""

    key: FactKey
    value: str = Field(description="'true'/'false' for yes-no facts, YYYY-MM for months, otherwise plain text.")
    confidence: float = Field(description="0.0 to 1.0: how clearly the text states this fact.")
    evidence: str = Field(description="Short exact quote from the description that supports the fact.")


class IntakeExtraction(BaseModel):
    """Gemini's structured output for intake. Only facts stated in the text are included."""

    facts: list[ExtractedFact]


class ProposedFact(BaseModel):
    """A fact proposed from free text. Always unconfirmed until the owner confirms it."""

    key: FactKey
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str
    confirmed: Literal[False] = False


class IntakeParseRequest(BaseModel):
    """Free-text description. With ``business_id`` the proposal is saved for confirm-update."""

    text: str = Field(min_length=1, max_length=2000)
    business_id: str | None = None


class IntakeParseResponse(BaseModel):
    """Proposed facts. ``proposal_id`` is set only when a ``business_id`` was given."""

    proposal_id: str | None = None
    proposed_facts: list[ProposedFact]
    dropped: list[str] = Field(
        default_factory=list, description="Model outputs rejected by validation, for debugging."
    )


class ConfirmUpdateRequest(BaseModel):
    """Owner's decision on a stored proposal.

    ``accepted`` lists the keys to apply (``None`` = all). ``edits`` overrides values for accepted
    keys. Keys not accepted stay as they were (unknown stays unknown).
    """

    proposal_id: str
    accepted: list[FactKey] | None = None
    edits: dict[FactKey, Any] = Field(default_factory=dict)


class ConfirmUpdateResponse(BaseModel):
    """The new profile version created from the confirmed facts."""

    proposal_id: str
    applied_keys: list[str]
    profile: BusinessProfile
