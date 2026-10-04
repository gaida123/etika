"""Route a chat question to one specialist agent.

Keyword rules first (free, deterministic). A small Gemini classifier call runs only when no
agent wins on keywords (no match, or a tie).
"""

import re
from typing import Literal

from pydantic import BaseModel

from app.agents.schemas import AgentName
from app.core.llm import StructuredGenerator

KEYWORDS: dict[AgentName, tuple[str, ...]] = {
    "employer": (
        "hire", "hiring", "hired", "employee", "employees", "employer", "staff", "worker", "workers",
        "helper", "payroll", "wage", "wages", "minimum wage", "worksafe", "worksafebc", "pay statement",
        "paystub", "contractor", "contractors",
    ),
    "tax": (
        "pst", "gst", "tax", "taxes", "sales tax", "charge tax", "invoice", "invoices", "small seller",
        "small supplier", "threshold", "revenue", "remit",
    ),
    "registration": (
        "licence", "license", "business licence", "business license", "register my name", "business name",
        "trading name", "bc registries", "registries", "business number", "bn", "permit", "sole proprietorship",
    ),
}

_PATTERNS: dict[AgentName, list[re.Pattern[str]]] = {
    agent: [re.compile(rf"\b{re.escape(word)}\b", re.I) for word in words] for agent, words in KEYWORDS.items()
}

CLASSIFIER_SYSTEM = """\
Pick the one specialist best suited to answer a new Vancouver sole proprietor's question:
- registration: business name registration, City of Vancouver business licence, CRA business number.
- tax: BC PST, GST, charging tax, sales thresholds.
- employer: hiring, employees, payroll, minimum wage, WorkSafeBC, pay statements, contractors.
Answer with the specialist name only."""


class RouteChoice(BaseModel):
    """Classifier output."""

    agent: Literal["registration", "tax", "employer"]


def route_by_keywords(question: str) -> AgentName | None:
    """The agent with the most keyword hits, or None on no match or a tie."""
    scores = {agent: sum(bool(p.search(question)) for p in patterns) for agent, patterns in _PATTERNS.items()}
    best = max(scores.values())
    winners = [agent for agent, score in scores.items() if score == best]
    return winners[0] if best > 0 and len(winners) == 1 else None


async def route_question(question: str, llm: StructuredGenerator) -> tuple[AgentName, str]:
    """Return (agent, method) where method is 'keywords' or 'classifier'."""
    agent = route_by_keywords(question)
    if agent is not None:
        return agent, "keywords"
    choice = await llm(prompt=question, system=CLASSIFIER_SYSTEM, schema=RouteChoice)
    return choice.agent, "classifier"
