"""Live chat for the Maya persona with REAL Gemini and stub knowledge services.

Run from backend/:  python scripts/smoke_chat.py ["your question"]
Roughly 3-5 Gemini calls.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import app  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="  [log] %(message)s")

DEFAULT_QUESTION = "I just hired a helper starting next week. Do I need to do anything for PST?"


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION
    with TestClient(app) as client:
        business_id = client.post("/dev/load-demo").json()["business_id"]
        resp = client.post("/chat", json={"business_id": business_id, "question": question})
        if resp.status_code != 200:
            print(f"FAILED {resp.status_code}: {resp.text}")
            sys.exit(1)
        body = resp.json()
        print(f"\nQ: {question}")
        print(f"agent={body['agent']} routed_by={body['routed_by']} insufficient={body['insufficient_evidence']}")
        print(f"A: {body['answer']}")
        for c in body["claims"]:
            print(f"  claim: {c['text']}  {c['chunk_ids']}")
        for s in body["sources"]:
            print(f"  source: {s['title']}")
        print(f"proposal_id={body['proposal_id']} proposed_facts={body['proposed_facts']}")
        print("\nTrace:")
        for t in body["trace"]:
            print(f"  {t['tool_name']:<22} {t['tool_output_summary']}")


if __name__ == "__main__":
    main()
