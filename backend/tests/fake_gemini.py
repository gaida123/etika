"""Scripted fake Gemini for agent tests. Reads requirement and chunk IDs out of the prompts.

Investigate turn 1: retrieve_evidence for every requirement in the prompt (+ calculators for tax,
+ one flag and one out-of-scope call for registration). Turn 2: replies DONE.
Report: one finding per requirement citing the evidence shown, plus one claim citing an invented
chunk and one out-of-scope finding, so validation has something to remove. The same parser handles
the legacy report prompt and the Phase 2 prefetch prompt: both use ``## REQ-ID:`` headers and
``Evidence [chunk_id]`` lines.

``requests`` counts every Gemini request (tool turns and structured calls); ``reports`` counts
structured report calls per agent, which is how the escalation cap is asserted.
"""

import re
from typing import Any

from google.genai import types
from pydantic import BaseModel

from app.agents.schemas import AgentReport, ClaimDraft, FindingDraft
from app.chat.router import RouteChoice
from app.chat.schemas import ChatAnswerDraft
from app.intake.schemas import ExtractedFact

REQ_RE = re.compile(r"\b((?:REG|TAX|EMP)-\d{2})\b")
SECTION_RE = re.compile(r"^## ((?:REG|TAX|EMP)-\d{2}):", re.M)
EVIDENCE_RE = re.compile(r"Evidence \[([^\]]+)\]")
INVENTED_CHUNK = "invented-chunk-id"


def agent_of(system: str) -> str:
    for name, marker in (("registration", "Registration"), ("tax", "Tax Registration"), ("employer", "Employer")):
        if f"You are the {marker}" in system:
            return name
    raise AssertionError("unknown agent prompt")


def call(tool: str, i: int, **args: Any) -> types.Part:
    return types.Part(function_call=types.FunctionCall(id=f"call-{i}", name=tool, args=args))


def response(parts: list[types.Part]) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=parts))]
    )


class FakeGemini:
    """Provides ``generate`` (tool turns) and ``structured`` (reports)."""

    def __init__(
        self,
        calls_per_turn: int | None = None,
        fail_report_for: str | None = None,
        classifier_choice: str = "registration",
        chat_without_evidence: bool = False,
        low_confidence_for: str | None = None,
        inject_status: bool = False,
        report_error: BaseException | None = None,
        voiced_summary: str = "Here is where you stand, in my own words.",
    ) -> None:
        self.voiced_summary = voiced_summary
        self.calls_per_turn = calls_per_turn
        self.fail_report_for = fail_report_for
        self.report_error = report_error
        self.classifier_choice = classifier_choice
        self.chat_without_evidence = chat_without_evidence
        self.low_confidence_for = low_confidence_for
        self.inject_status = inject_status
        self.requests = 0
        self.reports: dict[str, int] = {}
        self.report_prompts: list[str] = []
        self.report_systems: list[str] = []

    async def generate(
        self, contents: list[types.Content], config: types.GenerateContentConfig
    ) -> types.GenerateContentResponse:
        self.requests += 1
        agent = agent_of(str(config.system_instruction))
        prompt = contents[0].parts[0].text or ""  # type: ignore[index]
        if self.calls_per_turn is not None:
            req = REQ_RE.findall(prompt)[0]
            return response([call("get_requirement", i, requirement_id=req) for i in range(self.calls_per_turn)])
        if len(contents) > 1:
            return response([types.Part(text="DONE")])

        ids = list(dict.fromkeys(REQ_RE.findall(prompt)))
        parts = [call("retrieve_evidence", i, requirement_id=r, query=f"rules for {r}") for i, r in enumerate(ids)]
        if agent == "tax":
            parts += [
                call("get_calculator_result", 90, name="pst_small_seller_test"),
                call("get_calculator_result", 91, name="gst_small_supplier_test"),
            ]
        if agent == "registration":
            parts += [
                call("flag_for_review", 92, requirement_id="REG-02", reason="Home-based licence rules unclear"),
                call("retrieve_evidence", 93, requirement_id="EMP-01", query="sneaky out of scope"),
            ]
        return response(parts)

    async def structured(self, prompt: str, system: str, schema: type[BaseModel]) -> Any:
        self.requests += 1
        if schema is RouteChoice:
            return RouteChoice(agent=self.classifier_choice)
        if schema is ChatAnswerDraft:
            return self._chat_answer(prompt)
        assert schema is AgentReport
        agent = agent_of(system)
        if agent == self.fail_report_for:
            raise self.report_error or RuntimeError("simulated Gemini outage")
        self.reports[agent] = self.reports.get(agent, 0) + 1
        self.report_prompts.append(prompt)
        self.report_systems.append(system)
        confidence = 0.4 if agent == self.low_confidence_for else 0.9
        findings = []
        sections = SECTION_RE.split(prompt)[1:]
        for req_id, body in zip(sections[0::2], sections[1::2]):
            evidence = EVIDENCE_RE.findall(body)
            claims = [ClaimDraft(text=f"Official source says something about {req_id}.", chunk_ids=evidence[:1])]
            claims.append(ClaimDraft(text="Made-up claim.", chunk_ids=[INVENTED_CHUNK]))
            findings.append(
                self._finding(
                    requirement_id=req_id,
                    explanation=f"Explanation for {req_id}.",
                    claims=claims if evidence else [],
                    confidence=confidence,
                )
            )
        findings.append(self._finding(requirement_id="EMP-99", explanation="out of scope", claims=[]))
        return AgentReport(findings=findings, summary=self.voiced_summary)

    def _finding(
        self, requirement_id: str, explanation: str, claims: list[ClaimDraft], confidence: float = 1.0
    ) -> FindingDraft:
        """Build one draft, optionally trying to smuggle a status field past the schema."""
        payload: dict[str, Any] = {
            "requirement_id": requirement_id,
            "explanation": explanation,
            "claims": [c.model_dump() for c in claims],
            "flags": [],
            "confidence": confidence,
        }
        if self.inject_status:
            payload["status"] = "done"
        return FindingDraft.model_validate(payload)

    def _chat_answer(self, prompt: str) -> ChatAnswerDraft:
        evidence = [] if self.chat_without_evidence else EVIDENCE_RE.findall(prompt)
        claims = [ClaimDraft(text="The official source says so.", chunk_ids=evidence[:1])] if evidence else []
        claims.append(ClaimDraft(text="Made-up claim.", chunk_ids=[INVENTED_CHUNK]))
        question = prompt.split("<owner_question>")[-1]
        facts = []
        if "hired" in question.lower():
            facts.append(ExtractedFact(key="has_employees", value="true", confidence=0.95, evidence="hired"))
        return ChatAnswerDraft(answer="Grounded answer.", claims=claims, proposed_facts=facts)
