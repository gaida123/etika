"""End-to-end smoke test of the current workflow with REAL Gemini calls and stub services.

Run from backend/:  python scripts/smoke_workflow.py
Uses DATABASE_URL from .env (SQLite is fine). Makes 3 small Gemini calls.
"""

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import app  # noqa: E402
from app.contracts.facts import BusinessProfile  # noqa: E402
from app.core.services import get_services  # noqa: E402

MAYA_TEXT = (
    "I'm Maya Chen. I make soy candles in my Vancouver apartment and sell them as Wick & Co "
    "on Etsy and at weekend farmers markets. I also do some custom candle design work for weddings."
)
HIRING_TEXT = "Things are busy, so I've hired a part-time helper who starts next week for the holiday rush."


def show(title: str, data: Any) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(data, indent=2, default=str) if not isinstance(data, str) else data)


def summarize_assessment(profile_json: dict[str, Any]) -> dict[str, Any]:
    """Run the STUB applicability + scoring on a profile (no agents yet)."""
    services = get_services()
    profile = BusinessProfile.model_validate(profile_json)
    applicability = services.applicability.evaluate(profile)
    result = services.scoring.score([], applicability)
    return {
        "profile_version": profile.profile_version,
        "score": result.score,
        "now": [i.requirement_id for i in result.now],
        "next": [i.requirement_id for i in result.next],
        "later": [i.requirement_id for i in result.later],
        "missing_facts": sorted({f for a in applicability for f in a.missing_facts}),
    }


def check(resp: Any) -> dict[str, Any]:
    if resp.status_code >= 400:
        print(f"\nFAILED {resp.request.method} {resp.request.url}: {resp.status_code} {resp.text}")
        sys.exit(1)
    return resp.json()


def main() -> None:
    with TestClient(app) as client:
        show("GET /health", check(client.get("/health")))
        show("GET /health/gemini", check(client.get("/health/gemini")))

        maya = check(client.post("/dev/load-demo"))
        business_id = maya["business_id"]
        show("POST /dev/load-demo", {"business_id": business_id, "version": maya["profile_version"]})
        show("Stub assessment v1 (Maya fixture)", summarize_assessment(maya))

        parsed = check(client.post("/intake/parse", json={"text": MAYA_TEXT}))
        show("POST /intake/parse (first-time intake, nothing saved)", parsed)

        hiring = check(client.post("/intake/parse", json={"text": HIRING_TEXT, "business_id": business_id}))
        show("POST /intake/parse (hiring update, saved as proposal)", hiring)

        if not hiring["proposed_facts"]:
            print("\nGemini proposed no facts for the hiring text; stopping.")
            return
        confirmed = check(
            client.post(f"/profile/{business_id}/confirm-update", json={"proposal_id": hiring["proposal_id"]})
        )
        show("POST /profile/{id}/confirm-update (accept all)", {"applied_keys": confirmed["applied_keys"]})
        show("Stub assessment v2 (after confirming)", summarize_assessment(confirmed["profile"]))


if __name__ == "__main__":
    main()
