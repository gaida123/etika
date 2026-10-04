"""Pre-cache Maya's assessment (before and after the first hire) as a demo fallback.

Run from backend/ when you have Gemini quota:

    python scripts/warm_demo_cache.py

Writes two ``assessment_cache`` rows (same DATABASE_URL the API uses). On demo day, if any
agent hits a 429/503, ``POST /assess`` serves the matching cached result with ``cached=true``.

Do not run this with a fake model against the demo database — explanations would be placeholders.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.agents.cache import profile_fingerprint  # noqa: E402
from app.api.main import app  # noqa: E402
from app.contracts.facts import FactValue  # noqa: E402
from app.core.db import get_sessionmaker  # noqa: E402
from app.core.settings import get_settings  # noqa: E402
from app.intake import profile_service  # noqa: E402
from app.intake.profile_service import ProfileUpdate  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="  [log] %(message)s")


def _assess(client: TestClient, business_id: str, label: str) -> None:
    resp = client.post(f"/assess/{business_id}")
    if resp.status_code != 200:
        print(f"FAILED {label} {resp.status_code}: {resp.text}")
        sys.exit(1)
    body = resp.json()
    errors = [a["error"] for a in body["agents"] if a["error"]]
    print(
        f"{label}: cached={body['cached']} score={body['score']} "
        f"agents={[a['agent'] for a in body['agents']]}"
        + (f" errors={errors}" if errors else "")
    )
    if body["cached"] or errors:
        print("  (live run was incomplete; kept whatever was already cached for these facts)")


def main() -> None:
    settings = get_settings()
    print(f"DATABASE_URL={settings.database_url}  USE_STUBS={settings.use_stubs}")
    with TestClient(app) as client:
        before_id = client.post("/dev/load-demo").json()["business_id"]
        with get_sessionmaker()() as session:
            before = profile_service.get_latest(session, before_id)
            assert before is not None
            print(f"Maya (no hire) fingerprint={profile_fingerprint(before, settings.use_stubs)}")
        _assess(client, before_id, "Maya (no hire)")

        after_id = client.post("/dev/load-demo").json()["business_id"]
        with get_sessionmaker()() as session:
            after = profile_service.update_facts(
                session, after_id, ProfileUpdate(facts={"has_employees": FactValue(value=True, confirmed=True)})
            )
            print(f"Maya (hired)   fingerprint={profile_fingerprint(after, settings.use_stubs)}")
        _assess(client, after_id, "Maya (hired)")

    print("Demo fallback is ready. Re-run this after registry or stub-knowledge changes.")


if __name__ == "__main__":
    main()
