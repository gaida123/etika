"""Chat: routing, grounded answers, insufficient evidence and fact-update proposals (Gemini faked)."""

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.chat.router import route_by_keywords
from app.chat.service import WHO_TO_ASK
from app.core.llm import get_content_generator, get_llm
from tests.fake_gemini import INVENTED_CHUNK, FakeGemini


def use_fake(fake: FakeGemini) -> FakeGemini:
    app.dependency_overrides[get_content_generator] = lambda: fake.generate
    app.dependency_overrides[get_llm] = lambda: fake.structured
    return fake


def ask(client: TestClient, question: str) -> tuple[str, dict]:
    business_id = client.post("/dev/load-demo").json()["business_id"]
    resp = client.post("/chat", json={"business_id": business_id, "question": question})
    assert resp.status_code == 200, resp.text
    return business_id, resp.json()


@pytest.mark.parametrize(
    ("question", "agent"),
    [
        ("Do I need to charge PST on my candles?", "tax"),
        ("I'm hiring help for the holidays", "employer"),
        ("Do I need a business licence to sell from home?", "registration"),
        ("What should I do first?", None),
        ("If I hire someone, does GST change?", None),
    ],
)
def test_keyword_routing(question: str, agent: str | None) -> None:
    assert route_by_keywords(question) == agent


def test_grounded_answer_cites_only_retrieved_chunks(client: TestClient) -> None:
    use_fake(FakeGemini())
    _, body = ask(client, "Do I need to register for PST yet?")

    assert body["agent"] == "tax"
    assert body["routed_by"] == "keywords"
    assert body["insufficient_evidence"] is False
    assert body["answer"] == "Grounded answer."
    assert body["claims"] and all(INVENTED_CHUNK not in c["chunk_ids"] for c in body["claims"])
    assert body["sources"][0]["url"] == "TODO-official-url"
    assert body["proposal_id"] is None
    assert any(t["tool_name"] == "retrieve_evidence" for t in body["trace"])


def test_no_evidence_says_so_and_suggests_who_to_ask(client: TestClient) -> None:
    use_fake(FakeGemini(chat_without_evidence=True))
    _, body = ask(client, "How much is the PST penalty for late filing?")

    assert body["insufficient_evidence"] is True
    assert body["claims"] == []
    assert WHO_TO_ASK["tax"] in body["answer"]


def test_classifier_used_when_no_keywords(client: TestClient) -> None:
    use_fake(FakeGemini(classifier_choice="registration"))
    _, body = ask(client, "What should I do first?")
    assert body["agent"] == "registration"
    assert body["routed_by"] == "classifier"


def test_hiring_in_chat_proposes_then_confirm_and_reassess(client: TestClient) -> None:
    use_fake(FakeGemini())
    business_id, body = ask(client, "Good news, I've hired a part-time helper for the holidays!")

    assert body["agent"] == "employer"
    assert body["proposal_id"]
    assert body["proposed_facts"] == [
        {"key": "has_employees", "value": True, "confidence": 0.95, "evidence": "hired", "confirmed": False}
    ]
    assert client.get(f"/profile/{business_id}").json()["profile_version"] == 1  # nothing applied yet

    confirmed = client.post(
        f"/profile/{business_id}/confirm-update", json={"proposal_id": body["proposal_id"]}
    ).json()
    assert confirmed["profile"]["facts"]["has_employees"] == {"value": True, "confirmed": True}

    assessment = client.post(f"/assess/{business_id}").json()
    now = {i["requirement_id"] for i in assessment["now"]}
    assert {"EMP-01", "EMP-02", "EMP-03", "EMP-04", "EMP-05"} <= now


def test_chat_unknown_business_is_404(client: TestClient) -> None:
    use_fake(FakeGemini())
    assert client.post("/chat", json={"business_id": "nope", "question": "hi"}).status_code == 404
