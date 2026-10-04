"""Phase 7: persona voice. Gemini is faked; no live calls.

The point of these tests is that the persona is cosmetic by construction: it reaches exactly one
field, it cannot smuggle a number or a promise past code, and it is still present on a run that
makes zero Gemini requests.
"""

import json
import re
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.agents.base import render_numbers
from app.agents.personas import (
    PERSONAS,
    THE_COUNTER,
    THE_FOREMAN,
    THE_REGISTRAR,
    check_voice,
    persona_for,
    template_summary,
)
from app.core.settings import get_settings
from tests.fake_gemini import FakeGemini
from tests.test_agents import assess_maya, use_fake


@pytest.fixture(autouse=True)
def prefetch_mode(agent_mode: Callable[..., None]) -> None:
    agent_mode("prefetch")


@pytest.fixture
def no_finding_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every run reaches Gemini, so a voiced summary is actually written each time."""
    monkeypatch.setattr(get_settings(), "finding_cache_enabled", False)


def run(client: TestClient, **fake_kwargs: object) -> tuple[dict, FakeGemini]:
    fake = FakeGemini(**fake_kwargs)  # type: ignore[arg-type]
    use_fake(fake)
    return assess_maya(client), fake


def rows(body: dict) -> dict[str, dict]:
    return {a["agent"]: a for a in body["agents"]}


def is_template(agent: str, summary: str) -> bool:
    """True when this line came from the persona's templates rather than from Gemini."""
    persona = PERSONAS[agent]
    n_open = re.escape(persona.templates["n_open"]).replace(r"\{n\}", r"\d+").replace(r"\{first_title\}", ".+")
    fixed = (persona.templates["all_clear"], persona.templates["undetermined"])
    return summary in fixed or re.fullmatch(n_open, summary) is not None


# --- the characters ---------------------------------------------------------------------------


def test_each_agent_has_one_persona_with_a_real_specialisation() -> None:
    assert set(PERSONAS) == {"registration", "tax", "employer"}
    assert [p.display_name for p in (THE_REGISTRAR, THE_COUNTER, THE_FOREMAN)] == [
        "The Registrar",
        "The Counter",
        "The Foreman",
    ]
    for persona in PERSONAS.values():
        assert persona_for(persona.agent) is persona
        assert persona.voice_rules and persona.specialty
        assert {"all_clear", "n_open", "undetermined"} <= set(persona.templates)


def test_personas_are_exposed_on_every_agent_row(client: TestClient, no_finding_cache: None) -> None:
    body, _ = run(client)

    for name, row in rows(body).items():
        assert row["persona"]["display_name"] == PERSONAS[name].display_name
        assert row["persona"]["specialty"] == PERSONAS[name].specialty
        assert row["persona"]["avatar"] == PERSONAS[name].avatar
        assert row["summary_source"] == "model"
        assert row["summary"] == "Here is where you stand, in my own words."


def test_the_voice_block_is_scoped_to_the_summary_field(client: TestClient) -> None:
    _, fake = run(client)

    assert fake.report_systems and all("<persona_voice>" in s for s in fake.report_systems)
    assert all("`summary` field" in s for s in fake.report_systems)
    # each agent's own handle travels with its prompt, and only its own
    named = {next(p.display_name for p in PERSONAS.values() if p.display_name in s) for s in fake.report_systems}
    assert named == {p.display_name for p in PERSONAS.values()}


# --- the guardrail (Step 7.6) -----------------------------------------------------------------

GROUND = "You passed $10,000 in sales. 2 items."


def test_guardrail_accepts_a_line_grounded_in_the_findings() -> None:
    assert check_voice(THE_COUNTER, "You're past $10,000 in sales, so 2 items need you.", GROUND)
    assert check_voice(THE_COUNTER, "Nothing is over the line yet.", GROUND)


@pytest.mark.parametrize(
    "summary",
    [
        "I guarantee you're fully compliant.",
        "As your lawyer, I'd file this today.",
        "You have until October to file.",
        "You crossed the $30,000 threshold.",
        "   ",
    ],
    ids=["promise", "lawyer", "invented-date", "invented-number", "empty"],
)
def test_guardrail_rejects_promises_and_invented_facts(summary: str) -> None:
    assert check_voice(THE_COUNTER, summary, GROUND) is False


def test_a_rejected_line_falls_back_to_the_template_without_another_call(
    client: TestClient, no_finding_cache: None
) -> None:
    body, fake = run(client, voiced_summary="I guarantee you are fully compliant by October.")

    assert fake.reports == {"registration": 1, "tax": 1, "employer": 1}  # rejection never retries
    for name, row in rows(body).items():
        assert row["summary_source"] == "template"
        assert is_template(name, row["summary"])
        assert "guarantee" not in row["summary"].lower()


# --- zero-call runs (Step 7.4) ----------------------------------------------------------------


def test_a_fully_cached_run_still_speaks_in_character(client: TestClient) -> None:
    run(client)  # fills the Phase 3 finding cache
    body, fake = run(client)

    assert fake.requests == 0
    for name, row in rows(body).items():
        assert row["cached_findings"] > 0
        assert row["summary_source"] == "template"
        assert is_template(name, row["summary"])


def test_template_lines_cover_all_clear_open_and_undetermined() -> None:
    assert template_summary(THE_FOREMAN, 0, None) == THE_FOREMAN.templates["all_clear"]
    assert template_summary(THE_FOREMAN, 0, None, undetermined=True) == THE_FOREMAN.templates["undetermined"]
    open_line = template_summary(THE_FOREMAN, 2, "Register with WorkSafeBC")
    assert "2" in open_line and "Register with WorkSafeBC" in open_line
    # a count with no title still produces a sentence, never a stray placeholder
    assert "{" not in template_summary(THE_FOREMAN, 1, None)


# --- the persona changes nothing else ---------------------------------------------------------


def neutral(body: dict) -> list[dict]:
    return [
        {k: f[k] for k in ("requirement_id", "status", "explanation", "claims", "flags", "confidence")}
        for f in body["findings"]
    ]


def test_findings_are_identical_whatever_the_voice_says(client: TestClient, no_finding_cache: None) -> None:
    plain, _ = run(client, voiced_summary="Here is where you stand.")
    loud, _ = run(client, voiced_summary="I guarantee you're fully compliant forever.")

    assert neutral(loud) == neutral(plain)
    assert loud["score"] == plain["score"]
    assert rows(loud)["tax"]["summary"] != rows(plain)["tax"]["summary"]  # only the voice moved


def test_a_failed_agent_says_nothing_in_character(client: TestClient, no_finding_cache: None) -> None:
    body, _ = run(client, fail_report_for="tax")

    assert rows(body)["tax"]["error"]
    assert rows(body)["tax"]["summary"] == ""
    assert rows(body)["tax"]["persona"]["display_name"] == "The Counter"  # the character is still named
    assert rows(body)["registration"]["summary"]  # unaffected agents still speak


def test_calculator_amounts_reach_prompts_as_money() -> None:
    numbers = {"rolling_12_month_total": 2690.0, "threshold": 10000.0, "window_end": "2026-09", "max_single_quarter": 2070.5}
    assert render_numbers(numbers) == (
        "rolling_12_month_total: $2,690; threshold: $10,000; window_end: 2026-09; max_single_quarter: $2,070.50"
    )
    # The voice check still matches a formatted amount against the raw calculator float.
    ground = json.dumps({"numbers_used": numbers})
    assert check_voice(THE_COUNTER, "You're at $2,690 of the $10,000 line.", ground)
