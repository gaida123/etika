"""Base agent: scope, specialist prompt, tools, two-phase run, tool-call cap, trace.

Phase 1 (investigate): Gemini calls tools to gather evidence, calculator outputs and flags.
Phase 2 (report): a separate structured-output call turns what was gathered into one draft
finding per requirement. Code, not the model, has already decided applicability and sets status.
"""

from typing import Any, ClassVar

from google.genai import types

from app.agents.schemas import AgentName, AgentReport, AgentRunOutput
from app.agents.tools import AgentToolbox
from app.contracts.assessment import ApplicabilityResult
from app.contracts.facts import BusinessProfile
from app.core.llm import DEFAULT_TEMPERATURE, ContentGenerator, StructuredGenerator, describe_error
from app.core.services import Services

TOOL_LIMIT_MESSAGE = "Tool call limit reached. Stop calling tools."

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
    ) -> AgentRunOutput:
        """Investigate then report. Errors are captured on the output, never raised."""
        output = AgentRunOutput(agent=self.name, mode=mode, scope=scope)
        toolbox = AgentToolbox(self.name, assessment_id, profile, self.services, output, self.tool_names)
        try:
            await self.investigate(toolbox, self._investigate_prompt(output, profile), mode)
            report = await self.generate_structured(
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

    async def investigate(self, toolbox: AgentToolbox, prompt: str, mode: str | None) -> None:
        """Tool-calling loop (shared by assessment and chat), capped at ``max_tool_calls``."""
        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt(mode),
            temperature=DEFAULT_TEMPERATURE,
            tools=[types.Tool(function_declarations=toolbox.declarations())],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        contents: list[types.Content] = [types.Content(role="user", parts=[types.Part(text=prompt)])]
        calls = 0
        for _ in range(self.max_tool_calls + 1):
            response = await self.generate(contents, config)
            function_calls = response.function_calls or []
            if not function_calls or not response.candidates or response.candidates[0].content is None:
                break
            contents.append(response.candidates[0].content)
            parts: list[types.Part] = []
            for fc in function_calls:
                name, args = fc.name or "", dict(fc.args or {})
                if calls >= self.max_tool_calls:
                    result: dict[str, Any] = {"error": TOOL_LIMIT_MESSAGE}
                    toolbox.log(name, args, f"skipped: {TOOL_LIMIT_MESSAGE}")
                else:
                    calls += 1
                    toolbox.output.tool_calls = calls
                    result = toolbox.call(name, args)
                parts.append(types.Part(function_response=types.FunctionResponse(id=fc.id, name=name, response=result)))
            contents.append(types.Content(role="user", parts=parts))
            if calls >= self.max_tool_calls:
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


def facts_summary(profile: BusinessProfile) -> str:
    lines = [f"- legal_name: {profile.legal_name or 'unknown'}", f"- trading_name: {profile.trading_name or 'unknown'}"]
    for key, fact in profile.facts.items():
        lines.append(f"- {key}: {fact.value if fact.is_known else 'unknown'}")
    lines.append(f"- monthly_revenue: {len(profile.monthly_revenue)} month(s) entered")
    return "\n".join(lines)
