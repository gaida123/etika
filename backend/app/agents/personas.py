"""Agent personas (Phase 7): a voice for the human-facing summary only.

Each specialist agent gets one original character with a handle and a real specialisation. The
persona shapes exactly one field — ``AgentReport.summary`` — and nothing else. Findings,
explanations, claims, citations, status, score and scope stay neutral and code-decided, so turning
a persona off (or swapping one) can never change what the app says applies to the owner.

Three rules are enforced in code, not asked of the model:

1. No banned phrase may appear (``guarantee``, ``fully compliant``, ``as your lawyer``, ...).
2. Every number, amount and month in the summary must already appear in this run's findings,
   calculator results, or the counts code derived from them. The voice re-phrases; it never adds.
3. On any rejection — and on a fully cached run, where no model wrote a summary at all — code
   builds the line from the persona's templates. No retry, no extra Gemini request.

Personas are deliberately absent from the finding cache key (Step 7.5): findings are cached
neutral, and the summary is rebuilt on every run.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

from app.agents.schemas import FindingDraft

# Everything that must never show up in a voiced line, whoever is speaking. Per-persona `banned`
# entries are added to these.
BANNED_EVERYWHERE: tuple[str, ...] = (
    "guarantee",
    "guaranteed",
    "fully compliant",
    "as your lawyer",
    "legal advice",
    "i promise",
    "you're all set legally",
)

NUMBER_RE = re.compile(r"\d+(?:[,\d]*\d)?(?:\.\d+)?")
# "May" and "March" are left out on purpose: as bare words they are far more often English than a
# date, and a date written with them still carries a day or year, which rule 2 already checks.
MONTH_RE = re.compile(
    r"\b(january|february|april|june|july|august|september|october|november|december"
    r"|jan|feb|apr|jun|jul|aug|sept?|oct|nov|dec)\b",
    re.I,
)


@dataclass(frozen=True)
class Persona:
    """One specialist's character. ``agent`` ties it to exactly one agent name."""

    id: str
    agent: str
    display_name: str
    role_title: str
    specialty: str
    avatar: str  # key the frontend maps to a chibi illustration
    voice_rules: tuple[str, ...]
    banned: tuple[str, ...]
    templates: dict[str, str]

    @property
    def all_banned(self) -> tuple[str, ...]:
        return (*BANNED_EVERYWHERE, *self.banned)


THE_REGISTRAR = Persona(
    id="registrar_v1",
    agent="registration",
    display_name="The Registrar",
    role_title="Registration & licensing",
    specialty=(
        "Business name registration with BC Registries, the City of Vancouver business licence, "
        "and your CRA business number"
    ),
    avatar="registrar",
    voice_rules=(
        "Precise and orderly: mention things in the order an office would process them.",
        "Always name the office involved (BC Registries, the City of Vancouver, the CRA).",
        "Dry and understated. At most one light touch, never a joke at the owner's expense.",
    ),
    banned=("congratulations", "you're registered", "approved"),
    templates={
        "all_clear": "Nothing is sitting on my desk for you right now. I'll say so the moment that changes.",
        "n_open": "{n} registration item(s) are waiting on you. Start with {first_title}.",
        "undetermined": "I can't open a file on this yet — I'm missing a couple of details about your business.",
    },
)

THE_COUNTER = Persona(
    id="counter_v1",
    agent="tax",
    display_name="The Counter",
    role_title="Sales tax thresholds",
    specialty=(
        "BC PST and GST/HST registration, the small seller and small supplier tests, and how close "
        "your revenue is to each threshold"
    ),
    avatar="counter",
    voice_rules=(
        "Numbers first, then what they mean. Calm about thresholds, never alarmed.",
        "Say how close the owner is, and call any crossing month an estimate.",
        "Short sentences. No jargon the owner would have to look up.",
    ),
    banned=("you owe", "you don't have to pay tax", "tax-free"),
    templates={
        "all_clear": "Your numbers are under the lines that matter for now. I keep counting either way.",
        "n_open": "{n} tax item(s) need a decision from you. {first_title} is the one I'd look at first.",
        "undetermined": "I can't run the numbers yet — I need a bit more about what you sell and what you've made.",
    },
)

THE_FOREMAN = Persona(
    id="foreman_v1",
    agent="employer",
    display_name="The Foreman",
    role_title="Hiring & payroll",
    specialty=(
        "WorkSafeBC registration, your CRA payroll account, minimum wage, pay statements, payroll "
        "records, and employee vs contractor status"
    ),
    avatar="foreman",
    voice_rules=(
        "Warm and practical, like a site lead walking someone through their first day.",
        "Plain language about first hires. Say what switches on, and when.",
        "Encouraging but straight. Never minimise something the owner has to do.",
    ),
    banned=("don't worry about it", "nobody checks", "just pay cash"),
    templates={
        "all_clear": "Nothing changes for you on the hiring side today. When you take someone on, I'll walk you through it.",
        "n_open": "{n} thing(s) come with having people on the books. {first_title} is where I'd start.",
        "undetermined": "I can't tell yet whether any of this is live for you — let me know if you've taken anyone on.",
    },
)

PERSONAS: dict[str, Persona] = {p.agent: p for p in (THE_REGISTRAR, THE_COUNTER, THE_FOREMAN)}


def persona_for(agent: str) -> Persona | None:
    return PERSONAS.get(agent)


def voice_block(persona: Persona) -> str:
    """Appended to the report system prompt. Scoped to the ``summary`` field, nothing else."""
    return (
        "<persona_voice>\n"
        f"You are writing ONLY the `summary` field in the voice of {persona.display_name}, "
        f"{persona.role_title}.\n"
        "Style rules:\n"
        + "".join(f"- {rule}\n" for rule in persona.voice_rules)
        + "Never use these words or moves: "
        + ", ".join(persona.all_banned)
        + ".\n"
        "The summary is 1 to 2 sentences addressed to the owner as \"you\". It may only reference "
        "requirements, counts and facts that appear in the findings you are writing above. Do not "
        "add new legal claims, numbers, amounts or dates. Never claim the owner is compliant, and "
        "never promise an outcome.\n"
        "All other fields (explanation, claims, flags, confidence) stay neutral, factual and "
        "voice-free: they are shown to the owner as-is.\n"
        "</persona_voice>"
    )


def template_summary(persona: Persona, open_count: int, first_title: str | None, undetermined: bool = False) -> str:
    """The zero-call line. Used for cached runs and whenever a voiced summary is rejected."""
    if undetermined and not open_count:
        return persona.templates["undetermined"]
    if not open_count:
        return persona.templates["all_clear"]
    return persona.templates["n_open"].format(n=open_count, first_title=first_title or "the first one listed")


def grounding(drafts: list[FindingDraft], calculators: dict[str, Any], counts: list[int]) -> str:
    """Every word and number a voiced summary is allowed to draw on."""
    parts = [f"{d.requirement_id} {d.explanation} " + " ".join(c.text for c in d.claims) for d in drafts]
    parts += [json.dumps(calc, default=str) for calc in calculators.values()]
    parts += [str(n) for n in counts]
    return " ".join(parts)


def check_voice(persona: Persona, summary: str, ground: str) -> bool:
    """True when this summary is safe to show. Step 7.6, all three rules."""
    if not summary.strip():
        return False
    low = summary.lower()
    if any(phrase in low for phrase in persona.all_banned):
        return False
    if not _numbers(summary) <= _numbers(ground):
        return False
    return all(month.lower() in ground.lower() for month in MONTH_RE.findall(summary))


def _numbers(text: str) -> set[str]:
    """Numeric literals, normalised so ``1,000`` and ``1000.00`` compare equal."""
    found = set()
    for raw in NUMBER_RE.findall(text):
        value = raw.replace(",", "")
        if "." in value:
            value = value.rstrip("0").rstrip(".")
        found.add(value or "0")
    return found
