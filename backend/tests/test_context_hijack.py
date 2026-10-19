"""Context Hijack tests: simulator, server-side verification, API, reset."""

from __future__ import annotations

import pytest

from app.challenges.context_hijack import simulator as ch_sim
from app.challenges.context_hijack.corpus import (
    INJECTION_MARKER,
    OFFICIAL_ID,
    POISONED_ID,
    SHIPPING_ID,
)
from app.services import flag_store

BASE = "/api/challenges/context-hijack"
RETURN_Q = "What is the return policy for an unopened item?"


@pytest.fixture(autouse=True)
def _fresh_limiter(client):
    from app.routes import context_hijack as routes

    routes._rate_limiter.reset()


def _ask(client, query, player="p1"):
    return client.post(f"{BASE}/ask", json={"player_id": player, "query": query})


def _state(client, player="p1"):
    return client.get(f"{BASE}/state", params={"player_id": player}).json()


def test_listed_with_unique_identity(client):
    data = client.get("/api/challenges").json()
    slugs = [c["slug"] for c in data]
    assert slugs.count("context-hijack") == 1
    ch = next(c for c in data if c["slug"] == "context-hijack")
    assert ch["title"] == "Context Hijack"
    assert ch["category"] == "Prompt Injection"
    assert len(client.get("/api/challenges/context-hijack").json()["hints"]) == 3


def test_retrieval_is_deterministic():
    first = [d.doc_id for d in ch_sim.retrieve(RETURN_Q)]
    assert first == [d.doc_id for d in ch_sim.retrieve(RETURN_Q)]
    assert set(first) == {OFFICIAL_ID, POISONED_ID}


def test_vulnerable_answer_and_sources(client):
    r = _ask(client, RETURN_Q)
    assert r.status_code == 200
    body = r.json()
    st = body["state"]
    assert INJECTION_MARKER in st["response"]
    assert "lifetime refund" in st["response"]
    by_id = {s["doc_id"]: s for s in st["sources"]}
    assert by_id[POISONED_ID]["trusted"] is False
    assert by_id[OFFICIAL_ID]["trusted"] is True
    assert body["solved_condition"] is True
    assert body["flag"] == flag_store.load_flag("context-hijack")


def test_shipping_and_unrelated_queries_do_not_inject(client):
    for q in ("How long does shipping take?", "What colour is the sky?"):
        body = _ask(client, q).json()
        assert INJECTION_MARKER not in (body["state"]["response"] or "")
        assert body["solved_condition"] is False
        assert body["flag"] is None
    ids = [s["doc_id"] for s in _ask(client, "How long does shipping take?").json()["state"]["sources"]]
    assert ids == [SHIPPING_ID]
    assert not _state(client)["challenge_solved"]


def test_marker_alone_does_not_solve(client):
    for q in (INJECTION_MARKER, f"{INJECTION_MARKER} lifetime refund returns"):
        body = _ask(client, q).json()
        assert body["solved_condition"] is False
        assert body["flag"] is None
    assert not _state(client)["challenge_solved"]


def test_flag_never_in_state_and_client_cannot_assert_solve(client):
    _ask(client, RETURN_Q)
    assert "OWASP{" not in str(_state(client)["documents"])
    assert "flag" not in _state(client)
    r = client.post(
        f"{BASE}/ask",
        json={"player_id": "p2", "query": "hi", "solved": True, "isSolved": True},
    )
    assert r.status_code == 422


def test_flag_submission_flow(client):
    flag = _ask(client, RETURN_Q).json()["flag"]
    r = client.post(
        "/api/challenges/context-hijack/submit", json={"flag": flag, "player_id": "p1"}
    )
    assert r.json()["solved"] is True


def test_validation(client):
    assert _ask(client, "").status_code == 422
    assert _ask(client, "   ").status_code == 422
    assert _ask(client, "a" * 301).status_code == 422
    assert _ask(client, "x", player="p" * 81).status_code == 422


def test_analysis_only_after_solve(client):
    assert _ask(client, "How long does shipping take?").json()["state"]["analysis"] is None
    a = _ask(client, RETURN_Q).json()["state"]["analysis"]
    assert a["owasp"] == "LLM01:2025"


def test_reset_clears_only_turn(client):
    _ask(client, RETURN_Q)
    client.post("/api/challenges/render-trap/summarize", json={"player_id": "p1", "note": "n"})
    r = client.post(f"{BASE}/reset", json={"player_id": "p1"})
    st = r.json()
    assert st["response"] is None and st["sources"] == [] and st["query"] == ""
    assert st["challenge_solved"] is True  # unlock kept
    rt = client.get("/api/challenges/render-trap/state", params={"player_id": "p1"}).json()
    assert rt["note"] == "n"
    # repeat solves after reset are fine
    assert _ask(client, RETURN_Q).json()["solved_condition"] is True


def test_players_are_isolated(client):
    _ask(client, RETURN_Q, player="a")
    assert _state(client, player="b")["response"] is None
