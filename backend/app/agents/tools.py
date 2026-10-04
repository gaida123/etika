"""Tools agents can call (HANDOFF section 5.5).

Each tool is a plain Python method. The toolbox enforces scope (an agent can only touch its own
requirements), records every retrieved chunk (for citation validation) and writes a trace entry
per call. Tool outputs never include links: those come only from the registry, in code.
"""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from google.genai import types

from app.agents.schemas import AgentName, AgentRunOutput
from app.contracts.facts import BusinessProfile
from app.contracts.retrieval import RetrievalRequest
from app.contracts.trace import AgentTraceEntry
from app.core.services import Services

CALCULATOR_NAMES = ("pst_small_seller_test", "gst_small_supplier_test")
EVIDENCE_LIMIT = 3

_STR = {"type": "string"}

DECLARATIONS: dict[str, types.FunctionDeclaration] = {
    "retrieve_evidence": types.FunctionDeclaration(
        name="retrieve_evidence",
        description="Search official government sources for evidence about one requirement in your scope.",
        parameters_json_schema={
            "type": "object",
            "properties": {
                "requirement_id": {**_STR, "description": "Requirement ID, e.g. TAX-01."},
                "query": {**_STR, "description": "What you are looking for, in plain words."},
            },
            "required": ["requirement_id", "query"],
        },
    ),
    "get_requirement": types.FunctionDeclaration(
        name="get_requirement",
        description="Get registry details for one requirement in your scope: title, timing, gray areas, preparation items.",
        parameters_json_schema={
            "type": "object",
            "properties": {"requirement_id": _STR},
            "required": ["requirement_id"],
        },
    ),
    "get_profile_fact": types.FunctionDeclaration(
        name="get_profile_fact",
        description="Read one fact from the owner's profile. Unknown facts come back with known=false; never treat them as false.",
        parameters_json_schema={
            "type": "object",
            "properties": {"key": {**_STR, "description": "Fact key, e.g. sells or has_employees."}},
            "required": ["key"],
        },
    ),
    "get_calculator_result": types.FunctionDeclaration(
        name="get_calculator_result",
        description="Run a deterministic tax threshold calculator and get its outcome and the numbers it used.",
        parameters_json_schema={
            "type": "object",
            "properties": {"name": {"type": "string", "enum": list(CALCULATOR_NAMES)}},
            "required": ["name"],
        },
    ),
    "flag_for_review": types.FunctionDeclaration(
        name="flag_for_review",
        description="Flag a gray area on a requirement for human review. Do not resolve gray areas yourself.",
        parameters_json_schema={
            "type": "object",
            "properties": {"requirement_id": _STR, "reason": {**_STR, "description": "One sentence."}},
            "required": ["requirement_id", "reason"],
        },
    ),
}


class AgentToolbox:
    """Tool implementations bound to one agent run."""

    def __init__(
        self,
        agent: AgentName,
        assessment_id: str,
        profile: BusinessProfile,
        services: Services,
        output: AgentRunOutput,
        tool_names: tuple[str, ...],
    ) -> None:
        self.agent = agent
        self.assessment_id = assessment_id
        self.profile = profile
        self.services = services
        self.output = output
        self.tool_names = tool_names
        self.scope_ids = {a.requirement_id for a in output.scope}
        self._handlers: dict[str, Callable[..., dict[str, Any]]] = {
            "retrieve_evidence": self.retrieve_evidence,
            "get_requirement": self.get_requirement,
            "get_profile_fact": self.get_profile_fact,
            "get_calculator_result": self.get_calculator_result,
            "flag_for_review": self.flag_for_review,
        }

    def declarations(self) -> list[types.FunctionDeclaration]:
        """Function declarations for the tools this agent may use."""
        return [DECLARATIONS[name] for name in self.tool_names]

    def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Run one tool call and log it. Bad calls return an error dict instead of raising."""
        if name not in self.tool_names:
            result: dict[str, Any] = {"error": f"Tool {name} is not available to you."}
        else:
            try:
                result = self._handlers[name](**args)
            except TypeError as exc:
                result = {"error": f"Bad arguments for {name}: {exc}"}
        self.log(name, args, _summarize(name, result))
        return result

    def log(self, tool_name: str, tool_input: dict[str, Any], summary: str) -> None:
        """Append a trace entry for this agent."""
        self.output.trace.append(
            AgentTraceEntry(
                assessment_id=self.assessment_id,
                agent=self.agent,
                step=len(self.output.trace),
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output_summary=summary,
            )
        )

    # --- tools --------------------------------------------------------------------------------

    def retrieve_evidence(self, requirement_id: str, query: str) -> dict[str, Any]:
        if requirement_id not in self.scope_ids:
            return {"error": f"{requirement_id} is not in your scope."}
        result = self.services.retrieval.retrieve(
            RetrievalRequest(
                query=query,
                jurisdiction_ids=self.profile.jurisdiction_ids,
                segment_id=self.profile.segment_id,
                area=self.agent,
                requirement_ids=[requirement_id],
                as_of=datetime.now(timezone.utc),
                limit=EVIDENCE_LIMIT,
            )
        )
        ids = self.output.evidence_by_requirement.setdefault(requirement_id, [])
        for chunk in result.chunks:
            self.output.retrieved[chunk.chunk_id] = chunk
            if chunk.chunk_id not in ids:
                ids.append(chunk.chunk_id)
        return {
            "status": result.status,
            "chunks": [
                {"chunk_id": c.chunk_id, "title": c.title, "section": c.section_path, "text": c.text}
                for c in result.chunks
            ],
            "limitations": result.limitations,
        }

    def get_requirement(self, requirement_id: str) -> dict[str, Any]:
        if requirement_id not in self.scope_ids:
            return {"error": f"{requirement_id} is not in your scope."}
        req = self.services.registry.get(requirement_id)
        if req is None:
            return {"error": f"{requirement_id} not found."}
        applicability = next(a for a in self.output.scope if a.requirement_id == requirement_id)
        return {
            "id": req.id,
            "title": req.title,
            "requirement_type": req.requirement_type,
            "timing": req.timing,
            "applicability": applicability.status.value,
            "missing_facts": applicability.missing_facts,
            "depends_on": req.depends_on + req.depends_on_any,
            "preparation_items": req.preparation_items,
            "known_gray_areas": req.review_flags,
        }

    def get_profile_fact(self, key: str) -> dict[str, Any]:
        if key == "monthly_revenue":
            entries = [{"month": e.month, "amount": float(e.amount)} for e in self.profile.monthly_revenue]
            return {"key": key, "known": bool(entries), "entries": entries}
        if key in ("legal_name", "trading_name"):
            value = getattr(self.profile, key)
            return {"key": key, "known": value is not None, "value": value}
        fact = self.profile.fact(key)
        return {"key": key, "known": fact.is_known, "value": fact.value, "confirmed": fact.confirmed}

    def get_calculator_result(self, name: str) -> dict[str, Any]:
        if name not in CALCULATOR_NAMES:
            return {"error": f"Unknown calculator {name}."}
        result = self.services.calculators.run(name, self.profile)
        self.output.calculator_results[name] = result
        return result.model_dump(mode="json")

    def flag_for_review(self, requirement_id: str, reason: str) -> dict[str, Any]:
        if requirement_id not in self.scope_ids:
            return {"error": f"{requirement_id} is not in your scope."}
        self.output.flags.setdefault(requirement_id, []).append(reason.strip())
        return {"flagged": True}


def _summarize(name: str, result: dict[str, Any]) -> str:
    """One-line summary for the trace panel."""
    if "error" in result:
        return f"error: {result['error']}"
    if name == "retrieve_evidence":
        ids = ", ".join(c["chunk_id"] for c in result["chunks"]) or "none"
        return f"{result['status']}: {len(result['chunks'])} chunk(s) [{ids}]"
    if name == "get_calculator_result":
        crossing = f", est. crossing {result['estimated_crossing']}" if result.get("estimated_crossing") else ""
        return f"{result['name']}: {result['outcome']}{crossing}"
    if name == "get_profile_fact":
        if not result["known"]:
            return f"{result['key']} = unknown"
        if "entries" in result:
            return f"{result['key']}: {len(result['entries'])} month(s)"
        return f"{result['key']} = {result['value']}"
    if name == "get_requirement":
        return f"{result['id']}: {result['title']} ({result['applicability']})"
    if name == "flag_for_review":
        return "flagged for review"
    return "ok"
