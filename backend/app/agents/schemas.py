"""Agent-side models: what Gemini reports, and what one agent run hands to the orchestrator."""

from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.assessment import (
    ApplicabilityResult,
    AssessmentItem,
    CalculatorResult,
    Finding,
    Flag,
)
from app.contracts.registry import Area
from app.contracts.retrieval import RetrievedChunk
from app.contracts.trace import AgentTraceEntry

AgentName = Literal["registration", "tax", "employer"]
EmployerMode = Literal["full", "pre_hire"]


class ClaimDraft(BaseModel):
    """A claim as written by the model. Citation validation decides whether it survives."""

    text: str
    chunk_ids: list[str] = Field(description="IDs of evidence chunks that directly support this claim.")


class FindingDraft(BaseModel):
    """The model's explanation of one requirement. Status is NOT here: code sets it."""

    requirement_id: str
    explanation: str = Field(description="2-4 plain-English sentences for the owner.")
    claims: list[ClaimDraft]
    flags: list[str] = Field(description="Gray areas that need human review. Empty if none.")
    confidence: float = Field(description="0.0 to 1.0: how well the evidence supports the explanation.")


class AgentReport(BaseModel):
    """Structured output of the report phase: one finding per in-scope requirement."""

    findings: list[FindingDraft]


class AgentRunOutput(BaseModel):
    """Everything one agent produced in one run, before validation and scoring."""

    agent: AgentName
    mode: str | None = None
    scope: list[ApplicabilityResult]
    drafts: list[FindingDraft] = Field(default_factory=list)
    retrieved: dict[str, RetrievedChunk] = Field(default_factory=dict)
    evidence_by_requirement: dict[str, list[str]] = Field(default_factory=dict)
    flags: dict[str, list[str]] = Field(default_factory=dict)
    calculator_results: dict[str, CalculatorResult] = Field(default_factory=dict)
    trace: list[AgentTraceEntry] = Field(default_factory=list)
    tool_calls: int = 0
    error: str | None = None


class AgentRunSummary(BaseModel):
    """Per-agent summary shown alongside the assessment."""

    agent: AgentName
    mode: str | None
    tool_calls: int
    findings: int
    error: str | None = None


class AssessmentResponse(BaseModel):
    """Response of ``POST /assess/{business_id}`` (HANDOFF section 8.3)."""

    assessment_id: str
    business_id: str
    profile_version: int
    score: float | None
    area_scores: dict[Area, float | None]
    now: list[AssessmentItem]
    next: list[AssessmentItem]
    later: list[AssessmentItem]
    flags: list[Flag]
    findings: list[Finding]
    agents: list[AgentRunSummary]
    disclaimer: str = "General information, not legal advice."
