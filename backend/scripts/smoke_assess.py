"""Live assessment of the Maya persona with REAL Gemini agents and stub knowledge services.

Run from backend/:  python scripts/smoke_assess.py [--hire]
Roughly 6-12 Gemini calls. --hire first confirms has_employees=true (the demo climax).
"""

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import app  # noqa: E402
from app.contracts.facts import FactValue  # noqa: E402
from app.core.db import get_sessionmaker  # noqa: E402
from app.intake import profile_service  # noqa: E402
from app.intake.profile_service import ProfileUpdate  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="  [log] %(message)s")


def main() -> None:
    with TestClient(app) as client:
        business_id = client.post("/dev/load-demo").json()["business_id"]
        if "--hire" in sys.argv:
            with get_sessionmaker()() as session:
                profile_service.update_facts(
                    session, business_id, ProfileUpdate(facts={"has_employees": FactValue(value=True, confirmed=True)})
                )

        start = time.monotonic()
        resp = client.post(f"/assess/{business_id}")
        if resp.status_code != 200:
            print(f"FAILED {resp.status_code}: {resp.text}")
            sys.exit(1)
        body = resp.json()
        print(f"\nAssessment {body['assessment_id']} in {time.monotonic() - start:.0f}s")
        print(f"Score {body['score']}  area scores {body['area_scores']}")
        for col in ("now", "next", "later"):
            print(f"{col:>5}: {[i['requirement_id'] for i in body[col]]}")
        for a in body["agents"]:
            print(f"agent {a['agent']:<12} mode={a['mode']} tool_calls={a['tool_calls']} error={a['error']}")

        print("\nFindings:")
        for f in body["findings"]:
            print(f"- {f['requirement_id']} [{f['status']}] conf={f['confidence']:.2f} claims={len(f['claims'])}")
            print(f"    {f['explanation']}")
            for flag in f["flags"]:
                print(f"    FLAG: {flag}")

        print("\nTrace:")
        for t in client.get(f"/assessments/{body['assessment_id']}/trace").json():
            print(f"  {t['agent']:<12} {t['tool_name']:<22} {t['tool_output_summary']}")


if __name__ == "__main__":
    main()
