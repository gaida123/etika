"""Follow-up questions for missing facts (D2-04).

Missing facts come from the applicability engine (code). This module only words the questions.
Skipped questions leave the fact unknown; unknown is never false.
"""

from pydantic import BaseModel, Field

from app.contracts.assessment import ApplicabilityResult
from app.intake.fact_dictionary import FACT_SPECS

QUESTION_TEXT: dict[str, str] = {
    "legal_name": "What is your full legal name?",
    "trading_name": "What name does your business trade under, if any?",
    "trading_name_differs_from_legal_name": "Do you sell or invoice under a business name that is different from your own legal name?",
    "operates_in_vancouver": "Is your business based in the City of Vancouver?",
    "home_based": "Do you run the business from your home?",
    "online_only": "Do you sell only online (no markets, shops or in-person sales)?",
    "sells": "Do you sell goods, services, or both?",
    "has_established_premises": "Do you have a dedicated store, office or other business premises outside your home?",
    "sells_at_recurring_markets": "Do you sell regularly at markets, fairs or pop-ups?",
    "has_employees": "Have you hired anyone to work for your business (including someone starting soon)?",
    "plans_to_hire": "Are you planning to hire anyone?",
    "planned_hire_date": "Roughly which month do you expect to hire? (YYYY-MM)",
    "monthly_revenue": "What were your gross sales each month for the past 12 months? Estimates are fine.",
}

assert set(FACT_SPECS) <= set(QUESTION_TEXT), "every fact needs a question"


class FollowUpQuestion(BaseModel):
    """One question for a missing fact, with the requirements that need the answer."""

    fact_key: str
    question: str
    answer_type: str = Field(description="bool | enum | month | text | monthly_revenue")
    options: list[str] = Field(default_factory=list)
    needed_for: list[str] = Field(description="Requirement IDs that stay undetermined until answered.")


def follow_up_questions(applicability: list[ApplicabilityResult]) -> list[FollowUpQuestion]:
    """One question per missing fact, in fact-dictionary order, revenue last."""
    needed: dict[str, list[str]] = {}
    for a in applicability:
        for key in a.missing_facts:
            needed.setdefault(key, []).append(a.requirement_id)

    order = [*FACT_SPECS, "monthly_revenue"]
    questions = []
    for key in sorted(needed, key=lambda k: order.index(k) if k in order else len(order)):
        spec = FACT_SPECS.get(key)
        questions.append(
            FollowUpQuestion(
                fact_key=key,
                question=QUESTION_TEXT.get(key, f"Can you tell us about {key.replace('_', ' ')}?"),
                answer_type=spec.type if spec else "monthly_revenue" if key == "monthly_revenue" else "text",
                options=list(spec.options) if spec else [],
                needed_for=needed[key],
            )
        )
    return questions
