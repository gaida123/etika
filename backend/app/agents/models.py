"""Evidence pack models (Phase 2.1).

Everything an agent needs to write its findings, gathered by code before the single Gemini call.
Applicability is read-only here: it was decided by the applicability engine, never by the model.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.agents.retrieval_adapter import Chunk


class RequirementEvidence(BaseModel):
    """One in-scope requirement with everything code could look up about it."""

    requirement_id: str
    applicability: str = Field(description="Decided by code. Read-only for the model.")
    details: dict[str, Any] = Field(
        default_factory=dict, description="get_requirement() output: no links, no fees."
    )
    gray_areas: list[str] = Field(default_factory=list)
    chunks: list[Chunk] = Field(default_factory=list, description="Retrieved this run, so citable.")
    relevant_facts: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="get_profile_fact() output per key. Unknown facts keep known=false, never false.",
    )

    @property
    def missing_facts(self) -> list[str]:
        value = self.details.get("missing_facts") or []
        return [str(v) for v in value]


class EvidencePack(BaseModel):
    """What prefetch hands to the single report call. Built with zero Gemini requests."""

    agent: str
    mode: str | None = None
    requirements: list[RequirementEvidence] = Field(default_factory=list)
    calculators: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Tax agent only: PST and GST threshold results."
    )
    profile_summary: dict[str, Any] = Field(default_factory=dict)

    @property
    def chunk_count(self) -> int:
        return sum(len(r.chunks) for r in self.requirements)

    def without_chunks(self) -> list[str]:
        """Requirement IDs prefetch found no evidence for (escalation targets)."""
        return [r.requirement_id for r in self.requirements if not r.chunks]

    def subset(self, requirement_ids: set[str]) -> "EvidencePack":
        """The same pack narrowed to some requirements, for an escalation re-report."""
        return self.model_copy(
            update={"requirements": [r for r in self.requirements if r.requirement_id in requirement_ids]}
        )
