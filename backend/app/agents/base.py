"""Base agent: scope, specialist prompt, tools, cache, prefetch, single report call, trace.

Prefetch mode (``AGENT_MODE=prefetch``, Phase 2): code gathers every piece of evidence the agent
needs through the toolbox (zero Gemini calls), then the agent makes exactly ONE structured call to
write its findings. The tool loop survives only as a bounded escalation path for weak findings.
Phase 3 puts the per-requirement finding cache in front of that: requirements whose facts are
unchanged are answered from TiDB, and only the rest reach the single call (none means none).

Legacy mode (``AGENT_MODE=legacy``): the original two-phase run, a Gemini tool loop followed by a
report call. Unchanged, and still used by chat (which calls ``investigate`` directly).

In both modes applicability, status, score and scope come from code, never from the model.
"""

from typing import Any, ClassVar

from google.genai import types

from app.agents.finding_cache import CACHE, FindingCache
from app.agents.models import EvidencePack, RequirementEvidence
from app.agents.retrieval_adapter import (
    CHUNKS_PER_REQUIREMENT,
    Chunk,
    default_queries,
    fact_keys,
    to_chunk,
)
from app.agents.schemas import AgentName, AgentReport, AgentRunOutput, FindingDraft
from app.agents.tools import CALCULATOR_NAMES, AgentToolbox
from app.contracts.assessment import ApplicabilityResult
from app.contracts.facts import BusinessProfile
from app.core.llm import DEFAULT_TEMPERATURE, ContentGenerator, StructuredGenerator, describe_error
from app.core.services import Services
from app.core.settings import get_settings

TOOL_LIMIT_MESSAGE = "Tool call limit reached. Stop calling tools."
PREFETCH = "prefetch"
ESCALATION = "escalation"
ESCALATION_CONFIDENCE = 0.6
ESCALATION_TOOL_CALLS = 3
UNKNOWN_FACT = "unknown (we don't know this yet; never treat it as false)"

REPORT_RULES = """\
Write one finding per requirement listed, using exactly its requirement_id.
- explanation: 2-4 plain-English sentences addressed to the owner as "you", about their situation.
  Explain the applicability you were given; never contradict or re-decide it. Never mention
  "code", "calculator", "applicability", "the system" or requirement IDs; just say what it means for them.
- claims: each factual statement about the law, with chunk_ids copied exactly from the evidence
  shown. Only cite chunks shown for that requirement. Never cite anything else.
- If no evidence is shown for a requirement, say we could not find an official source for it,
  and give no claims.
- Never mention URLs, fees, deadlines, form numbers or dollar amounts unless they appear in the
  evidence text. Links and fees are shown separately by the app.
- flags: gray areas that need a human to check (e.g. ones you flagged during investigation).
- confidence: 0.0-1.0, how well the evidence supports your explanation.
- This is general information, not legal advice. Do not give advice beyond the evidence.
"""

PACK_RULES = """\
All the evidence code could gather is inside the <evidence> block below. You have no tools on this
turn: work only from what is shown.
- Write exactly one finding per requirement that appears in the block, and nothing else. Never add
  a requirement that is not shown.
- Never output a status, a score or a priority. Our rules already decided those.
- Cite only the chunk ids shown under the requirement you are writing about. Never invent an id,
  and never borrow an id from another requirement.
- A fact marked unknown means we do not know it. Never treat it as false, and never assume a value.
- If the chunks shown do not support something you want to say, say instead that we could not find
  an official source for it.
- Flag every gray area listed for a requirement that could apply to this owner. Never resolve one.
"""


class BaseAgent:
    """One specialist agent. Subclasses set the class attributes below."""

    name: ClassVar[AgentName]
    title: ClassVar[str]
    specialist_prompt: ClassVar[str]
    tool_names: ClassVar[tuple[str, ...]] = (
        "retrieve_evidence",
        "get_requirement",
        "get_profile_fact",
        "flag_for_review",
    )
    max_tool_calls: ClassVar[int] = 6

    def __init__(
        self, services: Services, generate: ContentGenerator, generate_structured: StructuredGenerator
    ) -> None:
        self.services = services
        self.generate = generate
        self.generate_structured = generate_structured

    # --- hooks for subclasses -----------------------------------------------------------------

    def mode_instructions(self, mode: str | None) -> str:
        """Extra instructions for the given mode (e.g. employer pre-hire)."""
        return ""

    def investigate_instructions(self) -> str:
        """Agent-specific investigation steps."""
        return ""

    # --- run ----------------------------------------------------------------------------------

    async def run(
        self,
        assessment_id: str,
        profile: BusinessProfile,
        scope: list[ApplicabilityResult],
        mode: str | None = None,
        report_generator: StructuredGenerator | None = None,
        cache: FindingCache | None = None,
    ) -> AgentRunOutput:
        """Reuse cached findings, then prefetch and report the rest in one call.

        Errors are captured on the output, never raised. When every requirement is cached the
        agent makes no Gemini request at all.
        """
        write_report = report_generator or self.generate_structured
        if get_settings().agent_mode == "legacy":
            return await self._run_legacy(assessment_id, profile, scope, mode, write_report)

        output = AgentRunOutput(agent=self.name, mode=mode, scope=scope)
        toolbox = AgentToolbox(self.name, assessment_id, profile, self.services, output, self.tool_names)
        try:
            reused = self._reuse_cached(toolbox, cache, profile, scope, mode)
            misses = [a for a in scope if a.requirement_id not in reused]
            if misses:
                pack = await self.prefetch(toolbox, profile, misses, mode)
                report = await write_report(
                    prompt=self._report_prompt_from_pack(pack),
                    system=f"{self.system_prompt(mode)}\n\n{REPORT_RULES}",
                    schema=AgentReport,
                )
                output.drafts = report.findings
                toolbox.log("report", {}, f"{len(report.findings)} draft finding(s)")
                if get_settings().escalation_enabled:
                    await self._escalate_weak_findings(toolbox, pack, output, mode, write_report)
                self._fill_cache(cache, profile, misses, mode, output)
            else:
                toolbox.log("report", {}, "no Gemini request: every requirement was cached", source=CACHE)
            output.drafts = [*output.drafts, *reused.values()]
        except Exception as exc:  # noqa: BLE001  (any failure becomes a visible, non-fatal error)
            output.error = describe_error(exc)
            toolbox.log("error", {}, output.error)
        return output

    async def _run_legacy(
        self,
        assessment_id: str,
        profile: BusinessProfile,
        scope: list[ApplicabilityResult],
        mode: str | None,
        write_report: StructuredGenerator,
    ) -> AgentRunOutput:
        """Pre-Phase-2 behaviour: a Gemini tool loop, then a report call."""
        output = AgentRunOutput(agent=self.name, mode=mode, scope=scope)
        toolbox = AgentToolbox(self.name, assessment_id, profile, self.services, output, self.tool_names)
        try:
            await self.investigate(toolbox, self._investigate_prompt(output, profile), mode)
            report = await write_report(
                prompt=self._report_prompt(output, profile, mode),
                system=f"{self.system_prompt(mode)}\n\n{REPORT_RULES}",
                schema=AgentReport,
            )
            output.drafts = report.findings
            toolbox.log("report", {}, f"{len(report.findings)} draft finding(s)")
        except Exception as exc:  # noqa: BLE001  (any failure becomes a visible, non-fatal error)
            output.error = describe_error(exc)
            toolbox.log("error", {}, output.error)
        return output

    # --- prefetch -----------------------------------------------------------------------------

    async def prefetch(
        self,
        toolbox: AgentToolbox,
        profile: BusinessProfile,
        scope: list[ApplicabilityResult],
        mode: str | None,
    ) -> EvidencePack:
        """Gather all evidence for the agent's scope through the toolbox. Zero Gemini calls.

        Every lookup goes through the toolbox so retrieved chunks stay registered for the strict
        citation filter and every step lands in the trace with ``source="prefetch"``. Retrieval for
        the whole scope goes out as one batch, because every query otherwise costs its own Gemini
        query embedding; the rest is sequential, since the toolbox mutates shared per-run state.
        """
        pack = EvidencePack(agent=self.name, mode=mode, profile_summary=profile_summary(profile))
        planned = [
            (applicability, req)
            for applicability in scope
            if (req := self.services.registry.get(applicability.requirement_id)) is not None
        ]
        toolbox.log(
            "prefetch",
            {"requirement_ids": [req.id for _, req in planned]},
            f"gathering evidence for {len(planned)} requirement(s)",
            source=PREFETCH,
        )
        toolbox.retrieve_evidence_many(
            [(req.id, query) for _, req in planned for query in default_queries(req)], source=PREFETCH
        )

        facts_read: dict[str, dict[str, Any]] = {}  # one lookup (and one trace entry) per fact key
        for applicability, req in planned:
            details = toolbox.call("get_requirement", {"requirement_id": req.id}, source=PREFETCH)
            keys = fact_keys(req) or list(profile.facts)
            for key in keys:
                if key not in facts_read:
                    facts_read[key] = toolbox.call("get_profile_fact", {"key": key}, source=PREFETCH)
            pack.requirements.append(
                RequirementEvidence(
                    requirement_id=req.id,
                    applicability=applicability.status.value,
                    details={k: v for k, v in details.items() if k != "error"},
                    gray_areas=list(req.review_flags),
                    chunks=chunks_for(toolbox.output, req.id),
                    relevant_facts={key: facts_read[key] for key in keys},
                )
            )

        if "get_calculator_result" in self.tool_names:
            for name in CALCULATOR_NAMES:
                result = toolbox.call("get_calculator_result", {"name": name}, source=PREFETCH)
                if "error" not in result:
                    pack.calculators[name] = result
        return pack

    # --- finding cache ------------------------------------------------------------------------

    def _reuse_cached(
        self,
        toolbox: AgentToolbox,
        cache: FindingCache | None,
        profile: BusinessProfile,
        scope: list[ApplicabilityResult],
        mode: str | None,
    ) -> dict[str, FindingDraft]:
        """Drafts this run can reuse, with their evidence put back on the run (Phase 3.4/3.5)."""
        if cache is None or not cache.enabled:
            return {}
        reused: dict[str, FindingDraft] = {}
        for applicability in scope:
            req = self.services.registry.get(applicability.requirement_id)
            if req is None:
                continue
            hit = cache.lookup(self.name, req, applicability, profile, mode)
            if hit is None:
                continue
            toolbox.register_chunks(req.id, hit.chunks)
            reused[req.id] = hit.draft
        toolbox.output.cached_findings = len(reused)
        if reused:
            toolbox.log(
                "finding_cache",
                {"requirement_ids": sorted(reused)},
                f"reused {len(reused)} finding(s) with no Gemini request",
                source=CACHE,
            )
        return reused

    def _fill_cache(
        self,
        cache: FindingCache | None,
        profile: BusinessProfile,
        misses: list[ApplicabilityResult],
        mode: str | None,
        output: AgentRunOutput,
    ) -> None:
        """Store the drafts this run wrote, after any escalation has improved them."""
        if cache is None or not cache.enabled:
            return
        drafts = {d.requirement_id: d for d in output.drafts}
        for applicability in misses:
            req = self.services.registry.get(applicability.requirement_id)
            draft = drafts.get(applicability.requirement_id)
            if req is None or draft is None:
                continue
            chunks = [
                output.retrieved[cid]
                for cid in output.evidence_by_requirement.get(req.id, [])
                if cid in output.retrieved
            ]
            cache.store(self.name, req, applicability, profile, mode, draft, chunks)

    # --- escalation ---------------------------------------------------------------------------

    async def _escalate_weak_findings(
        self,
        toolbox: AgentToolbox,
        pack: EvidencePack,
        output: AgentRunOutput,
        mode: str | None,
        write_report: StructuredGenerator,
    ) -> None:
        """One bounded investigate + re-report round for weak findings. Never raises.

        Called exactly once per agent run, so an assessment can never pay for two rounds. A
        failure here leaves the original drafts in place.
        """
        in_pack = {r.requirement_id for r in pack.requirements}
        targets = {d.requirement_id for d in output.drafts if d.confidence < ESCALATION_CONFIDENCE}
        targets = (targets | set(pack.without_chunks())) & in_pack
        if not targets:
            return

        trace_input = {"requirement_ids": sorted(targets), "escalated": True}
        try:
            await self.investigate(
                toolbox,
                self._escalation_prompt(pack, targets),
                mode,
                max_tool_calls=ESCALATION_TOOL_CALLS,
            )
            subset = self._refreshed(pack.subset(targets), output)
            report = await write_report(
                prompt=self._report_prompt_from_pack(subset),
                system=f"{self.system_prompt(mode)}\n\n{REPORT_RULES}",
                schema=AgentReport,
            )
            merged = {d.requirement_id: d for d in output.drafts}
            replaced = [d.requirement_id for d in report.findings if d.requirement_id in targets]
            for draft in report.findings:
                if draft.requirement_id in targets:
                    merged[draft.requirement_id] = draft
            output.drafts = list(merged.values())
            toolbox.log(
                "escalate", trace_input, f"re-reported {len(replaced)} finding(s)", source=ESCALATION
            )
        except Exception as exc:  # noqa: BLE001  (escalation is best-effort; keep the first drafts)
            toolbox.log("escalate", trace_input, f"escalation failed: {describe_error(exc)}", source=ESCALATION)

    def _refreshed(self, pack: EvidencePack, output: AgentRunOutput) -> EvidencePack:
        """Re-read chunks and investigation flags off the run output after escalation."""
        requirements = [
            r.model_copy(
                update={
                    "chunks": chunks_for(output, r.requirement_id),
                    "gray_areas": list(dict.fromkeys([*r.gray_areas, *output.flags.get(r.requirement_id, [])])),
                }
            )
            for r in pack.requirements
        ]
        return pack.model_copy(update={"requirements": requirements})

    # --- tool loop ----------------------------------------------------------------------------

    async def investigate(
        self,
        toolbox: AgentToolbox,
        prompt: str,
        mode: str | None,
        max_tool_calls: int | None = None,
    ) -> None:
        """Tool-calling loop (shared by assessment, chat and escalation), capped at ``max_tool_calls``."""
        limit = self.max_tool_calls if max_tool_calls is None else max_tool_calls
        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt(mode),
            temperature=DEFAULT_TEMPERATURE,
            tools=[types.Tool(function_declarations=toolbox.declarations())],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        contents: list[types.Content] = [types.Content(role="user", parts=[types.Part(text=prompt)])]
        calls = 0
        for _ in range(limit + 1):
            response = await self.generate(contents, config)
            function_calls = response.function_calls or []
            if not function_calls or not response.candidates or response.candidates[0].content is None:
                break
            contents.append(response.candidates[0].content)
            parts: list[types.Part] = []
            for fc in function_calls:
                name, args = fc.name or "", dict(fc.args or {})
                if calls >= limit:
                    result: dict[str, Any] = {"error": TOOL_LIMIT_MESSAGE}
                    toolbox.log(name, args, f"skipped: {TOOL_LIMIT_MESSAGE}")
                else:
                    calls += 1
                    toolbox.output.tool_calls += 1
                    result = toolbox.call(name, args)
                parts.append(types.Part(function_response=types.FunctionResponse(id=fc.id, name=name, response=result)))
            contents.append(types.Content(role="user", parts=parts))
            if calls >= limit:
                break

    # --- prompts ------------------------------------------------------------------------------

    def system_prompt(self, mode: str | None) -> str:
        """Specialist system prompt, shared by assessment and chat."""
        parts = [
            f"You are the {self.title} for a compliance navigator used by new sole proprietors in "
            "Vancouver, BC. You explain requirements using official evidence only.",
            self.specialist_prompt,
            "Code has already decided which requirements apply and calculated all thresholds. "
            "Never decide applicability or calculate numbers yourself. Gray areas are flagged, never resolved.",
            self.mode_instructions(mode),
        ]
        return "\n\n".join(p for p in parts if p)

    def _report_prompt_from_pack(self, pack: EvidencePack) -> str:
        """The single report call's prompt: everything code knows, in one delimited block."""
        lines = [f"Owner facts:\n{facts_summary_from_pack(pack)}", ""]
        if pack.mode:
            lines += [f"Mode: {pack.mode}", self.mode_instructions(pack.mode), ""]
        for name, calc in pack.calculators.items():
            lines.append(
                f"Calculator {name}: {calc.get('outcome')}; numbers: {calc.get('numbers_used')}; "
                f"estimated crossing (estimate only): {calc.get('estimated_crossing')}"
            )
        if pack.calculators:
            lines.append("")
        lines += [
            PACK_RULES,
            f"Requirements to report on ({len(pack.requirements)}): "
            + ", ".join(r.requirement_id for r in pack.requirements),
            "",
            "<evidence>",
        ]
        for req in pack.requirements:
            lines += self._requirement_block(req)
        lines.append("</evidence>")
        return "\n".join(lines)

    def _requirement_block(self, req: RequirementEvidence) -> list[str]:
        details = req.details
        title = details.get("title", req.requirement_id)
        lines = [
            f"## {req.requirement_id}: {title}",
            f"Type: {details.get('requirement_type', 'unknown')}. Timing: {details.get('timing', 'unknown')}. "
            f"Applicability (decided by code, read-only): {req.applicability}.",
        ]
        if req.missing_facts:
            lines.append(f"Facts we are missing: {', '.join(req.missing_facts)}")
        if req.relevant_facts:
            lines.append("Facts this requirement depends on:")
            lines += [f"- {key}: {render_fact(fact)}" for key, fact in req.relevant_facts.items()]
        if details.get("preparation_items"):
            lines.append(f"Preparation items: {'; '.join(details['preparation_items'])}")
        if req.gray_areas:
            lines.append(f"Gray areas to flag (never resolve): {'; '.join(req.gray_areas)}")
        if not req.chunks:
            lines.append("Evidence: NONE FOUND.")
        for chunk in req.chunks:
            lines.append(
                f"Evidence [{chunk.id}] {chunk.source_title} / {chunk.section_ref or ''}: {chunk.text}"
            )
        lines.append("")
        return lines

    def _escalation_prompt(self, pack: EvidencePack, targets: set[str]) -> str:
        by_id = {r.requirement_id: r for r in pack.requirements}
        lines = [
            "Our first pass could not explain these requirements well enough, either because no "
            "official source was found or because the evidence was weak. Dig for better evidence "
            "for these requirement IDs only:",
        ]
        for req_id in sorted(targets):
            req = by_id[req_id]
            title = req.details.get("title", req_id)
            found = f"{len(req.chunks)} chunk(s) already found" if req.chunks else "no evidence found yet"
            lines.append(f"- {req_id} {title} (applicability: {req.applicability}; {found})")
        lines += [
            "",
            "Owner facts:",
            facts_summary_from_pack(pack),
            "",
            "Call retrieve_evidence with different, more specific wording than a plain restatement "
            "of the title, and flag_for_review for any gray area that applies to this owner. You "
            f"have at most {ESCALATION_TOOL_CALLS} tool calls in total, so call several at once. "
            "When finished, reply with the single word DONE.",
        ]
        return "\n".join(lines)

    def _investigate_prompt(self, output: AgentRunOutput, profile: BusinessProfile) -> str:
        lines = ["Requirements in your scope (applicability decided by code):"]
        for a in output.scope:
            req = self.services.registry.get(a.requirement_id)
            if req is None:
                continue
            missing = f"; missing facts: {', '.join(a.missing_facts)}" if a.missing_facts else ""
            gray = f"; known gray areas: {'; '.join(req.review_flags)}" if req.review_flags else ""
            lines.append(f"- {req.id} {req.title} [{req.requirement_type}] applicability: {a.status.value}{missing}{gray}")
        lines += ["", "Owner facts:", facts_summary(profile), "", "Steps:"]
        lines.append("1. Call retrieve_evidence once for each requirement, with a specific query.")
        extra = self.investigate_instructions()
        if extra:
            lines.append(f"2. {extra}")
        lines.append(
            f"Then call flag_for_review for any gray area that applies to this owner. You have at most "
            f"{self.max_tool_calls} tool calls in total, so call several tools at once where you can. "
            "When finished, reply with the single word DONE."
        )
        return "\n".join(lines)

    def _report_prompt(self, output: AgentRunOutput, profile: BusinessProfile, mode: str | None) -> str:
        lines = [f"Owner facts:\n{facts_summary(profile)}", ""]
        if mode:
            lines += [f"Mode: {mode}", ""]
        for a in output.scope:
            req = self.services.registry.get(a.requirement_id)
            if req is None:
                continue
            lines.append(f"## {req.id}: {req.title}")
            lines.append(f"Type: {req.requirement_type}. Applicability (decided by code): {a.status.value}.")
            if a.missing_facts:
                lines.append(f"Missing facts: {', '.join(a.missing_facts)}")
            calc = output.calculator_results.get(req.trigger_rule or "")
            if calc:
                lines.append(f"Calculator {calc.name}: {calc.outcome}; numbers: {calc.numbers_used}; "
                             f"estimated crossing (estimate only): {calc.estimated_crossing}")
            for reason in output.flags.get(req.id, []):
                lines.append(f"Flagged during investigation: {reason}")
            chunk_ids = output.evidence_by_requirement.get(req.id, [])
            if not chunk_ids:
                lines.append("Evidence: NONE FOUND.")
            for cid in chunk_ids:
                chunk = output.retrieved[cid]
                lines.append(f"Evidence [{cid}] {chunk.title} / {chunk.section_path or ''}: {chunk.text}")
            lines.append("")
        return "\n".join(lines)


def chunks_for(output: AgentRunOutput, requirement_id: str) -> list[Chunk]:
    """Contract-shaped chunks retrieved for one requirement in this run, capped and deduped."""
    chunk_ids = dict.fromkeys(output.evidence_by_requirement.get(requirement_id, []))
    return [
        to_chunk(output.retrieved[cid], requirement_id)
        for cid in list(chunk_ids)[:CHUNKS_PER_REQUIREMENT]
        if cid in output.retrieved
    ]


def render_fact(fact: dict[str, Any]) -> str:
    """Render one ``get_profile_fact`` result. Unknown is never rendered as false."""
    if not fact.get("known"):
        return UNKNOWN_FACT
    if "entries" in fact:
        return f"{len(fact['entries'])} month(s) of revenue entered"
    return f"{fact.get('value')}"


def profile_summary(profile: BusinessProfile) -> dict[str, Any]:
    """The profile as structured data for the evidence pack, preserving unknown facts."""
    return {
        "legal_name": profile.legal_name,
        "trading_name": profile.trading_name,
        "jurisdiction_ids": list(profile.jurisdiction_ids),
        "segment_id": profile.segment_id,
        "facts": {
            key: {"known": fact.is_known, "value": fact.value if fact.is_known else None}
            for key, fact in profile.facts.items()
        },
        "revenue_months": len(profile.monthly_revenue),
    }


def facts_summary_from_pack(pack: EvidencePack) -> str:
    """``facts_summary`` for a pack, so the single call sees the same wording as the legacy path."""
    summary = pack.profile_summary
    facts: dict[str, dict[str, Any]] = summary.get("facts", {})
    lines = [
        f"- legal_name: {summary.get('legal_name') or 'unknown'}",
        f"- trading_name: {summary.get('trading_name') or 'unknown'}",
    ]
    lines += [f"- {key}: {fact['value'] if fact.get('known') else 'unknown'}" for key, fact in facts.items()]
    lines.append(f"- monthly_revenue: {summary.get('revenue_months', 0)} month(s) entered")
    return "\n".join(lines)


def facts_summary(profile: BusinessProfile) -> str:
    lines = [f"- legal_name: {profile.legal_name or 'unknown'}", f"- trading_name: {profile.trading_name or 'unknown'}"]
    for key, fact in profile.facts.items():
        lines.append(f"- {key}: {fact.value if fact.is_known else 'unknown'}")
    lines.append(f"- monthly_revenue: {len(profile.monthly_revenue)} month(s) entered")
    return "\n".join(lines)
