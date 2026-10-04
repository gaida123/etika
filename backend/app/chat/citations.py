"""Citation validation (HANDOFF section 5.7). Shared by assessment agents and chat.

Rules:
- Drop any finding outside the agent's scope, and duplicates (first one wins).
- Drop any claim that cites a chunk not retrieved in this run, or cites nothing.
- A finding left with no valid claims gets the standard "no official source" explanation, a flag,
  and low confidence. In-scope requirements the model skipped get the same treatment.
"""

from dataclasses import dataclass, field

from app.agents.schemas import ClaimDraft, FindingDraft

NO_SOURCE_EXPLANATION = (
    "We couldn't find an official source for this yet, so we can't explain it with confidence. "
    "Please check with the relevant authority (BC Registries, City of Vancouver, CRA, "
    "BC Ministry of Finance or WorkSafeBC) or a professional."
)
NO_SOURCE_FLAG = "No official source found; confirm with the relevant authority."
NO_SOURCE_CONFIDENCE = 0.2


@dataclass
class CitationReport:
    """Validated drafts keyed by requirement ID, plus what was removed (for the trace)."""

    drafts: dict[str, FindingDraft]
    dropped_claims: int = 0
    out_of_scope: list[str] = field(default_factory=list)
    without_source: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """One line for the agent trace."""
        parts = [f"{self.dropped_claims} uncited/invalid claim(s) dropped"]
        if self.out_of_scope:
            parts.append(f"out-of-scope findings dropped: {', '.join(self.out_of_scope)}")
        if self.without_source:
            parts.append(f"no official source: {', '.join(self.without_source)}")
        return "; ".join(parts)


def validate_citations(
    drafts: list[FindingDraft], scope_ids: list[str], retrieved_ids: set[str]
) -> CitationReport:
    """Apply the citation rules and return one validated draft per in-scope requirement."""
    report = CitationReport(drafts={})
    for draft in drafts:
        if draft.requirement_id not in scope_ids:
            report.out_of_scope.append(draft.requirement_id)
            continue
        if draft.requirement_id in report.drafts:
            continue
        valid = supported_claims(draft.claims, retrieved_ids)
        report.dropped_claims += len(draft.claims) - len(valid)
        if valid:
            report.drafts[draft.requirement_id] = draft.model_copy(update={"claims": valid})
        else:
            report.drafts[draft.requirement_id] = _no_source(draft.requirement_id, draft.flags)

    for req_id in scope_ids:
        if req_id not in report.drafts:
            report.drafts[req_id] = _no_source(req_id, [])
    report.without_source = [r for r in scope_ids if NO_SOURCE_FLAG in report.drafts[r].flags]
    return report


def supported_claims(claims: list[ClaimDraft], retrieved_ids: set[str]) -> list[ClaimDraft]:
    """Keep only claims whose every cited chunk was retrieved in this run."""
    return [c for c in claims if c.chunk_ids and all(cid in retrieved_ids for cid in c.chunk_ids)]


def _no_source(requirement_id: str, flags: list[str]) -> FindingDraft:
    return FindingDraft(
        requirement_id=requirement_id,
        explanation=NO_SOURCE_EXPLANATION,
        claims=[],
        flags=[*flags, NO_SOURCE_FLAG],
        confidence=NO_SOURCE_CONFIDENCE,
    )
