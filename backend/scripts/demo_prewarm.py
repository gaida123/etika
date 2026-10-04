"""Warm every cache the live demo touches, so the demo runs at ~0 Gemini requests.

Run from backend/ before you present, with the same .env the server uses:

    python scripts/demo_prewarm.py           # assessments only
    python scripts/demo_prewarm.py --chat    # also smoke-test the demo chat questions

For each demo scenario it creates a business exactly the way the intake page and dashboard do,
runs one assessment (cold: this is what fills the finding cache), then runs the same facts again
on a fresh business and checks that it costs 0 generation requests. The printed counts double as
the before/after numbers for the pitch.

The finding cache is keyed by facts, not by business, so any business entered on stage with the
same answers gets the cached findings. Keep SCENARIOS in step with the demo script. Re-run after
changing prompts, models or the corpus: each of those invalidates the cache on purpose.

Chat has no answer cache; ``--chat`` only proves the questions answer (about 2 requests each).
"""

import argparse
from datetime import date
import logging
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import app  # noqa: E402
from app.core.llm import request_counts  # noqa: E402
from app.core.settings import get_settings  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="  [log] %(message)s")

# Answers from the demo intake (see docs/PHASE7-HANDOFF.md, section 6). Facts are sent the way
# frontend/src/lib/intake.ts toProfileCreate builds them: only answered questions, all confirmed.
MAYA_INTAKE = {
    "operates_in_vancouver": True,
    "home_based": True,
    "sells": "goods",
    "sells_at_recurring_markets": True,
    "online_only": False,
    "has_employees": False,
    "plans_to_hire": True,
    "planned_hire_date": "2027-03",
    "trading_name_differs_from_legal_name": True,
}
# Stage 2 sales: $17,600 over 12 months, under the $30,000 line but trending toward it.
MAYA_SALES = [600, 750, 800, 950, 1100, 1250, 1400, 1600, 1850, 2100, 2400, 2800]

# (label, intake facts, dashboard answers, monthly sales or None)
SCENARIOS: list[tuple[str, dict[str, Any], dict[str, Any], list[int] | None]] = [
    ("1. Maya after intake", MAYA_INTAKE, {}, None),
    ("2. Maya answers premises + sales", MAYA_INTAKE, {"has_established_premises": False}, MAYA_SALES),
    ("3. Maya has hired", MAYA_INTAKE, {"has_established_premises": False, "has_employees": True}, MAYA_SALES),
]

CHAT_QUESTIONS = [
    "Do I need to register for GST or PST?",
    "Do I need to register my business name?",
    "What do I need to set up before I hire someone in March?",
]


def past_months(count: int = 12) -> list[str]:
    """The 12 months before this one, oldest first, as the dashboard's sales form offers them."""
    today = date.today()
    months = []
    for back in range(count, 0, -1):
        year, month = divmod(today.year * 12 + today.month - 1 - back, 12)
        months.append(f"{year}-{month + 1:02d}")
    return months


def build_business(client: TestClient, facts: dict[str, Any], answers: dict[str, Any], sales: list[int] | None) -> str:
    """Create the business the same way the app does: intake first, then dashboard answers."""
    body = {"trading_name": "Maya Makes", "facts": {k: {"value": v, "confirmed": True} for k, v in facts.items()}}
    resp = client.post("/profile", json=body)
    resp.raise_for_status()
    business_id = resp.json()["business_id"]
    if answers:
        client.patch(f"/profile/{business_id}", json={"facts": answers}).raise_for_status()
    if sales:
        revenue = [{"month": m, "amount": a} for m, a in zip(past_months(), sales, strict=True)]
        client.patch(f"/profile/{business_id}", json={"monthly_revenue": revenue}).raise_for_status()
    return business_id


def assess(client: TestClient, business_id: str) -> tuple[dict[str, Any], dict[str, int]]:
    before = request_counts()
    resp = client.post(f"/assess/{business_id}")
    resp.raise_for_status()
    after = request_counts()
    return resp.json(), {k: after.get(k, 0) - before.get(k, 0) for k in ("generate", "embed")}


def describe(body: dict[str, Any]) -> str:
    agents = body["agents"]
    cached = "/".join(str(a.get("cached_findings", 0)) for a in agents)
    errors = [f"{a['agent']}: {a['error']}" for a in agents if a.get("error")]
    note = f"  ERRORS {errors}" if errors else ""
    return f"cached findings {cached}{' (served from assessment fallback)' if body.get('cached') else ''}{note}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--chat", action="store_true", help="also ask the demo chat questions")
    args = parser.parse_args()

    settings = get_settings()
    print(f"use_stubs={settings.use_stubs} finding_cache={settings.finding_cache_enabled} gemini_rpm={settings.gemini_rpm}")
    if settings.use_stubs:
        print("USE_STUBS=true: nothing real to warm. Set USE_STUBS=false in backend/.env.")
        return 1

    ok = True
    with TestClient(app) as client:
        for label, facts, answers, sales in SCENARIOS:
            print(f"\n{label}")
            body, cold = assess(client, build_business(client, facts, answers, sales))
            print(f"  first run   generate={cold['generate']} embed={cold['embed']}  {describe(body)}")
            body, warm = assess(client, build_business(client, facts, answers, sales))
            print(f"  rerun       generate={warm['generate']} embed={warm['embed']}  {describe(body)}")
            if warm["generate"]:
                ok = False
                print("  ! rerun still called Gemini: something in the cache key differs between runs")

        if args.chat:
            print("\nChat (no answer cache; this only proves the answers come back grounded)")
            business_id = build_business(client, MAYA_INTAKE, {"has_established_premises": False}, MAYA_SALES)
            for question in CHAT_QUESTIONS:
                before = request_counts()
                resp = client.post("/chat", json={"business_id": business_id, "question": question})
                spent = request_counts().get("generate", 0) - before.get("generate", 0)
                if resp.status_code != 200:
                    ok = False
                    print(f"  FAILED {resp.status_code} {question}: {resp.text[:200]}")
                    continue
                answer = resp.json()
                grounded = "grounded" if not answer["insufficient_evidence"] else "NO SOURCE FOUND"
                print(f"  [{grounded}, {spent} generate] {question}")

    total = request_counts()
    print(f"\nTotal this run: generate={total.get('generate', 0)} embed={total.get('embed', 0)}")
    print("Demo caches are warm." if ok else "Finished with problems; see the lines marked above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
