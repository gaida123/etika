"""Chat request/response models."""

from pydantic import BaseModel, Field

from app.agents.schemas import AgentName, ClaimDraft
from app.contracts.assessment import Claim, SourceLink
from app.contracts.trace import AgentTraceEntry
from app.intake.schemas import ExtractedFact, ProposedFact


class ChatRequest(BaseModel):
    """A question from the owner about their business."""

    business_id: str
    question: str = Field(min_length=1, max_length=1000)


class ChatAnswerDraft(BaseModel):
    """Gemini's structured chat answer, before citation and fact validation."""

    answer: str = Field(description="Plain-English answer to the owner, 2-5 sentences.")
    claims: list[ClaimDraft]
    proposed_facts: list[ExtractedFact] = Field(
        description="New facts the owner stated about their own business in this message. Empty if none."
    )


class ChatResponse(BaseModel):
    """Grounded answer. ``proposal_id`` is set when the owner mentioned new facts to confirm."""

    conversation_id: str
    agent: AgentName
    routed_by: str
    answer: str
    insufficient_evidence: bool
    claims: list[Claim]
    sources: list[SourceLink]
    proposal_id: str | None = None
    proposed_facts: list[ProposedFact] = Field(default_factory=list)
    trace: list[AgentTraceEntry] = Field(default_factory=list)
    disclaimer: str = "General information, not legal advice."
