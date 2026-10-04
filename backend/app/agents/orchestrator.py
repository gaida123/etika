"""Orchestrator (HANDOFF section 5.4). Plain Python, not an LLM.

1. Code evaluates applicability.
2. Pick agents: registration and tax always; employer full / pre-hire / skipped.
3. Reuse cached findings, prefetch the rest in parallel, then serialize their Gemini report calls.
4. Validate citations, set status from applicability (code), merge flags.
5. Score (Developer 1), enrich cards with sources and threshold progress, persist findings + trace.
"""

import asyncio
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.employer import EmployerAgent
from app.agents.finding_cache import FindingCache
from app.agents.personas import persona_for
from app.agents.registration import RegistrationAgent
from app.agents.retrieval_adapter import kb_version
from app.agents.schemas import AgentRunOutput, AgentRunSummary, AssessmentResponse, PersonaInfo
from app.agents.tax import TaxAgent
from app.chat.citations import NO_SOURCE_FLAG, validate_citations
from app.contracts.assessment import (
    ApplicabilityResult,
    ApplicabilityStatus,
    AssessmentItem,
    Claim,
    Finding,
    FindingStatus,
    SourceLink,
)
from app.contracts.facts import BusinessProfile
from app.contracts.retrieval import RetrievedChunk
from app.contracts.trace import AgentTraceEntry
from app.core.llm import ContentGenerator, StructuredGenerator
from app.core.models import AgentRunRow, FindingRow
from app.core.services import Services
from app.core.settings import get_settings

LOW_CONFIDENCE = 0.6
LOW_CONFIDENCE_FLAG = "Low confidence: check with a professional."
AGENT_UNAVAILABLE_EXPLANATION = (
    "We couldn't check official sources for this right now because the AI service was unavailable. "
    "Whether it applies to you was still decided by our rules. Please re-run the assessment."
)
AGENT_UNAVAILABLE_FLAG = "Agent unavailable during this run; re-run the assessment."

STATUS_FROM_APPLICABILITY: dict[ApplicabilityStatus, FindingStatus] = {
    ApplicabilityStatus.required_now: "not_done",
    ApplicabilityStatus.upcoming: "not_yet_required",
    ApplicabilityStatus.undetermined: "undetermined",
}

PROGRESS_CALCULATORS: dict[str, tuple[str, str]] = {
    "TAX-01": ("pst_small_seller_test", "rolling_12_month_total"),
    "TAX-02": ("gst_small_supplier_test", "last_four_quarters_total"),
}


class Orchestrator:
    """Runs one assessment end to end."""

    def __init__(
        self, services: Services, generate: ContentGenerator, generate_structured: StructuredGenerator
    ) -> None:
        self.services = services
        self.generate_structured = generate_structured
        self.agents: dict[str, BaseAgent] = {
            cls.name: cls(services, generate, generate_structured)
            for cls in (RegistrationAgent, TaxAgent, EmployerAgent)
        }

    def plan(
        self, profile: BusinessProfile, applicability: list[ApplicabilityResult]
    ) -> list[tuple[BaseAgent, list[ApplicabilityResult], str | None]]:
        """Which agents run, with which requirements, in which mode."""
        planned = []
        for name, agent in self.agents.items():
            scope = [
                a
                for a in applicability
                if a.status != ApplicabilityStatus.not_applicable
                and (req := self.services.registry.get(a.requirement_id)) is not None
                and req.area == name
            ]
            mode = employer_mode(profile) if name == "employer" else None
            if scope and mode != "skip":
                planned.append((agent, scope, mode))
        return planned

    async def assess(self, session: Session, profile: BusinessProfile) -> AssessmentResponse:
        assessment_id = str(uuid.uuid4())
        applicability = self.services.applicability.evaluate(profile)
        planned = self.plan(profile, applicability)
        cache = self._finding_cache(session)
        # Keep retrieval/prefetch concurrent, but avoid a burst of three large structured
        # reports against one provider capacity pool. This gate also covers escalation
        # re-reports in the same assessment.
        report_gate = asyncio.Semaphore(1)

        async def queued_report(*args: Any, **kwargs: Any) -> Any:
            async with report_gate:
                return await self.generate_structured(*args, **kwargs)

        # Tests/stubs should stay fast. Live requests offset starts slightly so semantic
        # retrieval batches do not hit Gemini in the exact same instant; report calls use
        # the gate above.
        stagger_seconds = 0.0 if get_settings().use_stubs else get_settings().agent_start_stagger_seconds
        plan_entry = AgentTraceEntry(
            assessment_id=assessment_id,
            agent="orchestrator",
            step=0,
            tool_name="plan",
            tool_input={
                "profile_version": profile.profile_version,
                "agent_start_stagger_seconds": stagger_seconds,
                "report_concurrency": 1,
                "finding_cache": cache.enabled,
            },
            tool_output_summary="running "
            + ", ".join(f"{a.name}" + (f" ({m})" if m else "") for a, _, m in planned),
        )

        async def run_staggered(
            index: int, agent: BaseAgent, scope: list[ApplicabilityResult], mode: str | None
        ) -> AgentRunOutput:
            if index and stagger_seconds > 0:
                await asyncio.sleep(stagger_seconds * index)
            return await agent.run(
                assessment_id, profile, scope, mode, report_generator=queued_report, cache=cache
            )

        outputs: list[AgentRunOutput] = await asyncio.gather(
            *(run_staggered(index, agent, scope, mode) for index, (agent, scope, mode) in enumerate(planned))
        )

        findings: list[Finding] = []
        seen: set[str] = set()
        for output in outputs:
            for finding in self._finalize(output, assessment_id):
                if finding.requirement_id not in seen:
                    seen.add(finding.requirement_id)
                    findings.append(finding)

        result = self.services.scoring.score(findings, applicability)
        chunks = {cid: c for o in outputs for cid, c in o.retrieved.items()}
        by_req = {f.requirement_id: f for f in findings}

        def enrich(items: list[AssessmentItem]) -> list[AssessmentItem]:
            return [self._enrich(i, by_req.get(i.requirement_id), chunks, profile) for i in items]

        _persist(session, assessment_id, findings, outputs, [plan_entry])
        return AssessmentResponse(
            assessment_id=assessment_id,
            business_id=profile.business_id,
            profile_version=profile.profile_version,
            score=result.score,
            area_scores=result.area_scores,
            now=enrich(result.now),
            next=enrich(result.next),
            later=enrich(result.later),
            flags=result.flags,
            findings=findings,
            agents=[_summary_of(o) for o in outputs],
        )

    def _finding_cache(self, session: Session) -> FindingCache:
        """The per-requirement draft cache for one assessment.

        The corpus version decides whether reuse is safe at all, so a retrieval service that
        cannot identify itself disables the cache instead of failing the assessment.
        """
        settings = get_settings()
        try:
            corpus_version: str | None = kb_version(self.services.retrieval)
        except Exception:  # noqa: BLE001 - cache availability must never break an assessment
            corpus_version = None
        return FindingCache(
            session=session,
            kb_version=corpus_version,
            model=settings.gemini_model,
            gates={
                "use_stubs": settings.use_stubs,
                "allow_unreviewed_knowledge": settings.allow_unreviewed_knowledge,
                "allow_candidate_requirement_mappings": settings.allow_candidate_requirement_mappings,
                "allow_draft_registry": settings.allow_draft_registry,
            },
            enabled=settings.finding_cache_enabled and settings.agent_mode != "legacy",
        )

    def _finalize(self, output: AgentRunOutput, assessment_id: str) -> list[Finding]:
        """Validate citations and turn drafts into Findings with code-decided status."""
        scope_ids = [a.requirement_id for a in output.scope]
        report = validate_citations(output.drafts, scope_ids, set(output.retrieved))
        output.trace.append(
            AgentTraceEntry(
                assessment_id=assessment_id,
                agent=output.agent,
                step=len(output.trace),
                tool_name="validate_citations",
                tool_output_summary=report.summary(),
            )
        )

        findings = []
        for a in output.scope:
            draft = report.drafts[a.requirement_id]
            flags = [*draft.flags, *output.flags.get(a.requirement_id, [])]
            explanation = draft.explanation
            if output.error:
                explanation = AGENT_UNAVAILABLE_EXPLANATION
                flags = [AGENT_UNAVAILABLE_FLAG]
            elif draft.confidence < LOW_CONFIDENCE and NO_SOURCE_FLAG not in flags:
                flags.append(LOW_CONFIDENCE_FLAG)
            findings.append(
                Finding(
                    requirement_id=a.requirement_id,
                    status=STATUS_FROM_APPLICABILITY[a.status],
                    explanation=explanation,
                    claims=[Claim(text=c.text, chunk_ids=c.chunk_ids) for c in draft.claims],
                    flags=list(dict.fromkeys(f for f in flags if f)),
                    confidence=min(max(draft.confidence, 0.0), 1.0),
                )
            )
        return findings

    def _enrich(
        self,
        item: AssessmentItem,
        finding: Finding | None,
        chunks: dict[str, RetrievedChunk],
        profile: BusinessProfile,
    ) -> AssessmentItem:
        """Add cited sources and threshold progress (both from code, never from the model)."""
        update: dict[str, Any] = {}
        if finding:
            cited = dict.fromkeys(cid for c in finding.claims for cid in c.chunk_ids)
            update["sources"] = [
                SourceLink(
                    title=chunks[cid].title,
                    url=chunks[cid].url,
                    section_path=chunks[cid].section_path,
                    retrieved_at=chunks[cid].retrieved_at,
                )
                for cid in cited
                if cid in chunks
            ]
        if item.requirement_id in PROGRESS_CALCULATORS:
            name, current_key = PROGRESS_CALCULATORS[item.requirement_id]
            calc = self.services.calculators.run(name, profile)
            if calc.outcome != "undetermined":
                update["progress"] = {
                    "current": calc.numbers_used.get(current_key),
                    "threshold": calc.numbers_used.get("threshold"),
                    "estimated_crossing": calc.estimated_crossing,
                    "outcome": calc.outcome,
                }
        return item.model_copy(update=update)


def _summary_of(output: AgentRunOutput) -> AgentRunSummary:
    """One agent's row in the response, including its persona (display only, Phase 7)."""
    persona = persona_for(output.agent)
    return AgentRunSummary(
        agent=output.agent,
        mode=output.mode,
        tool_calls=output.tool_calls,
        findings=len(output.scope),
        cached_findings=output.cached_findings,
        persona=(
            PersonaInfo(
                id=persona.id,
                display_name=persona.display_name,
                role_title=persona.role_title,
                specialty=persona.specialty,
                avatar=persona.avatar,
            )
            if persona
            else None
        ),
        # A failed agent has nothing grounded to re-voice, so it says nothing in character.
        summary="" if output.error else output.summary,
        summary_source=output.summary_source,
        error=output.error,
    )


def employer_mode(profile: BusinessProfile) -> str:
    """full if has employees; skip only if the owner confirmed no employees AND no plans; else pre_hire."""
    has_emp, plans = profile.fact("has_employees"), profile.fact("plans_to_hire")
    if has_emp.is_known and has_emp.value is True:
        return "full"
    if has_emp.is_known and has_emp.value is False and plans.is_known and plans.value is False:
        return "skip"
    return "pre_hire"


def _persist(
    session: Session,
    assessment_id: str,
    findings: list[Finding],
    outputs: list[AgentRunOutput],
    extra_trace: list[AgentTraceEntry],
) -> None:
    agent_of = {a.requirement_id: o.agent for o in outputs for a in o.scope}
    for f in findings:
        session.add(
            FindingRow(
                assessment_id=assessment_id,
                requirement_id=f.requirement_id,
                agent=agent_of.get(f.requirement_id, "unknown"),
                status=f.status,
                explanation=f.explanation,
                claims=[c.model_dump() for c in f.claims],
                cited_chunk_ids=list(dict.fromkeys(cid for c in f.claims for cid in c.chunk_ids)),
                flags=f.flags,
                confidence=f.confidence,
            )
        )
    for entry in [*extra_trace, *(e for o in outputs for e in o.trace)]:
        session.add(
            AgentRunRow(
                assessment_id=entry.assessment_id,
                agent=entry.agent,
                step=entry.step,
                tool_name=entry.tool_name,
                tool_input=entry.tool_input,
                tool_output_summary=entry.tool_output_summary,
                created_at=entry.created_at,
            )
        )
    session.commit()


def get_trace(session: Session, assessment_id: str) -> list[AgentTraceEntry]:
    """All trace entries for an assessment, in the order they were recorded."""
    rows = session.scalars(
        select(AgentRunRow).where(AgentRunRow.assessment_id == assessment_id).order_by(AgentRunRow.id)
    )
    return [
        AgentTraceEntry(
            assessment_id=r.assessment_id,
            agent=r.agent,
            step=r.step,
            tool_name=r.tool_name,
            tool_input=r.tool_input or {},
            tool_output_summary=r.tool_output_summary,
            created_at=r.created_at,
        )
        for r in rows
    ]
