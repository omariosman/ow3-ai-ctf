"""Poisoned Memory tests: fixtures, ranking, server-side verification, reset."""

from __future__ import annotations

import pytest

from app.challenges.poisoned_memory import simulator as pm_sim
from app.challenges.poisoned_memory.corpus import (
    AUTHORITATIVE_ID,
    FALSE_COMPONENT,
    POISON_MARKER,
    POISONED_ID,
    RECORDS,
    SHIPPING_ID,
)
from app.services import flag_store

BASE = "/api/challenges/poisoned-memory"
Q = "Which replacement component is approved for the Northstar Mini?"


@pytest.fixture(autouse=True)
def _fresh_limiter(client):
    from app.routes import poisoned_memory as routes

    routes._rate_limiter.reset()


def _ask(client, q, player="p1"):
    return client.post(f"{BASE}/ask", json={"player_id": player, "query": q})


def _inspect(client, rid=POISONED_ID, player="p1"):
    return client.post(f"{BASE}/inspect", json={"player_id": player, "record_id": rid})


def _evidence(client, marker, player="p1"):
    return client.post(f"{BASE}/evidence", json={"player_id": player, "marker": marker})


def _state(client, player="p1"):
    return client.get(f"{BASE}/state", params={"player_id": player}).json()


def test_listed_with_unique_identity(client):
    data = client.get("/api/challenges").json()
    assert [c["slug"] for c in data].count("poisoned-memory") == 1
    ch = next(c for c in data if c["slug"] == "poisoned-memory")
    assert ch["title"] == "Poisoned Memory"
    assert ch["category"] == "Data and Model Poisoning"
    assert len(client.get("/api/challenges/poisoned-memory").json()["hints"]) == 3


def test_fixture_records_labelled():
    by_id = {r.record_id: r for r in RECORDS}
    assert by_id[AUTHORITATIVE_ID].trust == "authoritative"
    assert by_id[AUTHORITATIVE_ID].source == "Northstar Manufacturer Manual"
    assert by_id[POISONED_ID].trust == "unverified"
    assert by_id[POISONED_ID].source == "Community Tips Archive"
    assert by_id[SHIPPING_ID].trust == "verified"
    assert "ignore" not in by_id[POISONED_ID].content.lower()


def test_ranking_is_deterministic_and_flawed():
    first = [(r.record.record_id, r.score) for r in pm_sim.rank(Q)]
    assert first == [(r.record.record_id, r.score) for r in pm_sim.rank(Q)]
    assert [i for i, _ in first] == [POISONED_ID, AUTHORITATIVE_ID]


def test_vulnerable_answer_and_ranking(client):
    st = _ask(client, Q).json()
    assert FALSE_COMPONENT in st["response"]
    ranks = {r["record_id"]: r for r in st["retrieved"]}
    assert ranks[POISONED_ID]["rank"] == 1 and ranks[POISONED_ID]["trust"] == "unverified"
    assert ranks[AUTHORITATIVE_ID]["rank"] == 2
    assert POISON_MARKER not in str(st)


def test_inspect_reveals_marker_and_trust(client):
    d = _inspect(client).json()["record"]
    assert POISON_MARKER in d["note"] and d["trust"] == "unverified"
    assert POISON_MARKER not in _inspect(client, AUTHORITATIVE_ID).text
    assert _inspect(client, "nope").status_code == 404


def test_unrelated_queries_do_not_poison(client):
    for q in ("When will my order ship?", "What colour is the sky?"):
        st = _ask(client, q).json()
        assert FALSE_COMPONENT not in (st["response"] or "")
        assert POISONED_ID not in [r["record_id"] for r in st["retrieved"]]
    ids = [r["record_id"] for r in _ask(client, "northstar shipping delivery").json()["retrieved"]]
    assert ids == [SHIPPING_ID]


def test_marker_alone_does_not_solve(client):
    _inspect(client)
    _ask(client, POISON_MARKER)
    assert _evidence(client, POISON_MARKER).json()["solved_condition"] is False
    _ask(client, f"{POISON_MARKER} northstar mini replacement component approved")
    assert _evidence(client, POISON_MARKER).json()["solved_condition"] is False
    assert not _state(client)["challenge_solved"]


def test_non_poisoned_query_cannot_solve(client):
    _inspect(client)
    _ask(client, "northstar shipping delivery")
    body = _evidence(client, POISON_MARKER).json()
    assert body["solved_condition"] is False and body["flag"] is None


def test_requires_inspection_and_correct_marker(client):
    _ask(client, Q)
    assert _evidence(client, POISON_MARKER).json()["solved_condition"] is False
    _inspect(client, AUTHORITATIVE_ID)
    assert _evidence(client, POISON_MARKER).json()["solved_condition"] is False
    _inspect(client)
    assert _evidence(client, "wrong").json()["solved_condition"] is False


def test_full_solve_via_flag_flow(client):
    _ask(client, Q)
    _inspect(client)
    body = _evidence(client, POISON_MARKER).json()
    assert body["solved_condition"] is True
    assert body["flag"] == flag_store.load_flag("poisoned-memory")
    assert body["state"]["analysis"]["owasp"] == "LLM04:2025"
    r = client.post(f"{BASE}/submit", json={"flag": body["flag"], "player_id": "p1"})
    assert r.json()["solved"] is True


def test_flag_not_in_state_and_client_cannot_assert_solve(client):
    _ask(client, Q)
    assert "OWASP{" not in str(_state(client))
    assert _state(client)["analysis"] is None
    r = client.post(f"{BASE}/ask", json={"player_id": "p2", "query": "hi", "isSolved": True})
    assert r.status_code == 422


def test_validation(client):
    assert _ask(client, "").status_code == 422
    assert _ask(client, "a" * 201).status_code == 422
    assert _ask(client, "x", player="p" * 81).status_code == 422


def test_reset_clears_only_this_challenge(client):
    _ask(client, Q)
    _inspect(client)
    _evidence(client, POISON_MARKER)
    client.post("/api/challenges/render-trap/summarize", json={"player_id": "p1", "note": "n"})
    st = client.post(f"{BASE}/reset", json={"player_id": "p1"}).json()
    assert st["response"] is None and st["retrieved"] == [] and st["query"] == ""
    assert st["challenge_solved"] is True
    rt = client.get("/api/challenges/render-trap/state", params={"player_id": "p1"}).json()
    assert rt["note"] == "n"
    assert _evidence(client, POISON_MARKER).json()["solved_condition"] is False


def test_players_are_isolated(client):
    _ask(client, Q, player="a")
    _inspect(client, player="a")
    assert _evidence(client, POISON_MARKER, player="b").json()["solved_condition"] is False
