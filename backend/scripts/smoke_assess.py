"""Live assessment of the Maya persona through the production-shaped API flow.

Run from backend/:  python scripts/smoke_assess.py [--hire]
Roughly 3 report calls plus batched retrieval embeddings. ``--hire`` first saves
``has_employees=true`` as a new profile version (the demo climax). The script
creates a new Maya profile and assessment in the configured database; unlike the
old development helper, it works when ``USE_STUBS=false``.
"""

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import app  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="  [log] %(message)s")
MAYA_PROFILE_PATH = Path(__file__).resolve().parents[2] / "contracts" / "examples" / "maya_profile.json"


def _require_success(response: object) -> dict[str, object]:
    """Return an API body or stop without printing potentially sensitive settings."""
    status_code = getattr(response, "status_code", 500)
    if status_code < 400:
        return getattr(response, "json")()
    print(f"FAILED: API returned {status_code}.")
    sys.exit(1)


def main() -> None:
    with TestClient(app) as client:
        maya = json.loads(MAYA_PROFILE_PATH.read_text(encoding="utf-8"))
        created = _require_success(client.post("/profile", json=maya))
        business_id = str(created["business_id"])
        if "--hire" in sys.argv:
            updated = _require_success(
                client.patch(f"/profile/{business_id}", json={"facts": {"has_employees": True}})
            )
            print(f"Maya profile updated to version {updated['profile_version']} with a confirmed first hire.")

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
