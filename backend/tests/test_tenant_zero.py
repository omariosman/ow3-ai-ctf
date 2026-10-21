"""Tenant Zero tests: simulator, solve validation, API, reset, isolation."""

from __future__ import annotations

import pytest

from app.challenges.tenant_zero import simulator as sim
from app.challenges.tenant_zero.data import ACTING_TENANT, CANARY, CONVERSATIONS
from app.challenges.tenant_zero.simulator import Policy
from app.services import flag_store

BASE = "/api/challenges/tenant-zero"
HARDENED = {
    "enforce_ownership": True,
    "scope_search_to_tenant": True,
    "redact_sensitive_fields": True,
    "enforcement_enabled": True,
}
A = ACTING_TENANT


@pytest.fixture(autouse=True)
def _fresh_limiter(client):
    from app.routes import tenant_zero as routes

    routes._rate_limiter.reset()


def _open(client, cid, player="p1"):
    return client.post(f"{BASE}/open", json={"player_id": player, "conversation_id": cid})


def _summary(client, cid, player="p1"):
    return client.post(f"{BASE}/summary", json={"player_id": player, "conversation_id": cid})


def _search(client, q, player="p1"):
    return client.post(f"{BASE}/search", json={"player_id": player, "query": q})


def _policy(client, policy=HARDENED, player="p1"):
    return client.post(f"{BASE}/policy", json={"player_id": player, **policy})


def _verify(client, player="p1"):
    return client.post(f"{BASE}/verify", json={"player_id": player}).json()


def _state(client, player="p1"):
    return client.get(f"{BASE}/state", params={"player_id": player}).json()


# --- data / simulator -----------------------------------------------------------


def test_fixture_data_is_fictional_and_owned():
    assert {c.tenant for c in CONVERSATIONS} == {"tenant-alpha", "tenant-beta"}
    for c in CONVERSATIONS:
        assert c.contact_email.endswith("@example.test") and c.account.startswith("ACCT-FAKE-")
    assert any(CANARY in m for c in CONVERSATIONS if c.tenant == "tenant-beta" for m in c.messages)


def test_vulnerable_policy_leaks_every_surface():
    p = sim.VULNERABLE_POLICY
    r = sim.open_conversation(p, A, "conv-2001")
    assert r.allowed and r.cross_tenant and CANARY in str(r.conversation)
    assert any(x["tenant"] == "tenant-beta" for x in sim.search(p, A, "contract"))
    s = sim.summarize(p, A, "conv-2001")
    assert "beta.owner@example.test" in s.conversation["summary"]


def test_ownership_denial_is_uniform_and_leaks_nothing():
    p = Policy(enforce_ownership=True, enforcement_enabled=True)
    foreign = sim.open_conversation(p, A, "conv-2001")
    missing = sim.open_conversation(p, A, "conv-9999")
    assert foreign == missing and foreign.message == sim.DENIED and foreign.conversation is None


def test_scoped_search_and_redaction():
    p = Policy(True, True, True, True)
    assert all(r["tenant"] == A for r in sim.search(p, A, "contract renewal outage"))
    text = sim.summarize(p, A, "conv-1002").conversation["summary"]
    assert "@" not in text and "ACCT-FAKE" not in text and "[redacted" in text


def test_master_switch_makes_flags_cosmetic():
    p = Policy(True, True, True, False)
    assert sim.open_conversation(p, A, "conv-2001").allowed
    assert not all(c["passed"] for c in sim.verify_policy(p))


def test_hardened_passes_and_variants():
    assert all(c["passed"] for c in sim.verify_policy(Policy(True, True, True, True)))
    for partial in (Policy(False, True, True, True), Policy(True, False, True, True), Policy(True, True, False, True)):
        assert not all(c["passed"] for c in sim.verify_policy(partial))
    assert not all(c["passed"] for c in sim.verify_policy(sim.VULNERABLE_POLICY))


def test_own_access_works_when_hardened():
    p = Policy(True, True, True, True)
    assert sim.open_conversation(p, A, "conv-1001").allowed
    assert any(r["tenant"] == A for r in sim.search(p, A, "password"))


def test_query_validation_and_policy_validation():
    for bad in ("", "   ", "x" * 61):
        with pytest.raises(sim.QueryInvalid):
            sim.normalize_query(bad)
    with pytest.raises(sim.PolicyInvalid):
        sim.validate_policy(Policy(enforce_ownership="yes"))


# --- API / solve validation ---------------------------------------------------


def test_listed_with_unique_identity(client):
    data = client.get("/api/challenges").json()
    assert [c["slug"] for c in data].count("tenant-zero") == 1
    ch = next(c for c in data if c["slug"] == "tenant-zero")
    assert ch["title"] == "Tenant Zero" and ch["category"] == "Sensitive Information Disclosure"
    assert len(client.get("/api/challenges/tenant-zero").json()["hints"]) == 3
    for slug in ("model-mirror", "release-roulette", "render-trap", "model-crate",
                 "context-hijack", "trace-leak", "poisoned-memory", "token-storm"):
        assert slug in [c["slug"] for c in data]


def test_initial_state(client):
    st = _state(client)
    assert st["tenant_name"] == "Tenant Alpha" and st["leak_demonstrated"] is False
    assert [c["conv_id"] for c in st["own_conversations"]] == ["conv-1001", "conv-1002"]
    assert "OWASP{" not in str(st) and CANARY not in str(st)


def test_leak_is_recorded_server_side(client):
    own = _open(client, "conv-1001").json()
    assert own["allowed"] and not own["state"]["leak_demonstrated"]
    body = _open(client, "conv-2001").json()
    assert body["allowed"] and CANARY in str(body["conversation"])
    assert body["state"]["leak_demonstrated"] is True


def test_search_leak_recorded(client):
    assert _search(client, "contract").json()["state"]["leak_demonstrated"] is True


def test_typing_canary_does_not_solve(client):
    _policy(client)  # hardened first, so typing the marker retrieves nothing foreign
    for text in (CANARY, CANARY.replace("_", " ")):
        assert _search(client, text).json()["results"] == []
    body = _verify(client)
    assert body["solved_condition"] is False  # no leak evidence recorded
    assert not _state(client)["challenge_solved"]


def test_leak_alone_does_not_solve(client):
    _open(client, "conv-2001")
    body = _verify(client)
    assert body["solved_condition"] is False and body["flag"] is None


def test_hardening_without_leak_does_not_solve(client):
    _policy(client)
    body = _verify(client)
    assert all(c["passed"] for c in body["state"]["checks"])
    assert body["solved_condition"] is False and body["flag"] is None


def test_applying_policy_without_verifying_does_not_solve(client):
    _open(client, "conv-2001")
    st = _policy(client).json()
    assert st["hardening_verified"] is False and st["challenge_solved"] is False


def test_cosmetic_policy_fails(client):
    _open(client, "conv-2001")
    _policy(client, {**HARDENED, "enforcement_enabled": False})
    assert _verify(client)["solved_condition"] is False


def test_full_solve_and_flag_flow(client):
    _open(client, "conv-2001")
    _policy(client)
    body = _verify(client)
    assert body["solved_condition"] is True
    assert body["flag"] == flag_store.load_flag("tenant-zero")
    assert body["state"]["analysis"]["owasp"] == "LLM02:2025"
    r = client.post(f"{BASE}/submit", json={"flag": body["flag"], "player_id": "p1"})
    assert r.json()["solved"] is True


def test_hardened_live_behaviour(client):
    _policy(client)
    denied = _open(client, "conv-2001").json()
    assert denied["allowed"] is False and denied["conversation"] is None
    assert denied["message"] == _open(client, "conv-9999").json()["message"]
    assert _open(client, "conv-1001").json()["allowed"]
    assert all(r["tenant"] == "tenant-alpha" for r in _search(client, "contract password").json()["results"])
    assert _state(client)["leak_demonstrated"] is False


def test_policy_change_voids_verification(client):
    _open(client, "conv-2001")
    _policy(client)
    assert _verify(client)["state"]["hardening_verified"] is True
    st = _policy(client, {**HARDENED, "redact_sensitive_fields": False}).json()
    assert st["hardening_verified"] is False and st["checks"] == []


def test_client_cannot_fabricate_evidence(client):
    for extra in ({"solved": True}, {"isSolved": True}, {"tenant": "tenant-beta"},
                  {"role": "admin"}, {"leak_demonstrated": True}, {"checks": []}):
        assert client.post(f"{BASE}/open", json={"player_id": "p1", "conversation_id": "conv-1001", **extra}).status_code == 422
        assert client.post(f"{BASE}/search", json={"player_id": "p1", "query": "x", **extra}).status_code == 422
        assert client.post(f"{BASE}/verify", json={"player_id": "p1", **extra}).status_code == 422
        assert client.post(f"{BASE}/policy", json={"player_id": "p1", **HARDENED, **extra}).status_code == 422
    assert _state(client)["leak_demonstrated"] is False


def test_validation(client):
    for bad in ("", "conv-1", "conv-12345", "../etc/passwd", "conv-100a", "CONV-1001"):
        assert _open(client, bad).status_code == 422
    assert _search(client, "").status_code == 422
    assert _search(client, "x" * 61).status_code == 422
    assert _open(client, "conv-1001", player="p" * 81).status_code == 422
    assert _policy(client, {**HARDENED, "enforcement_enabled": "yes"}).status_code == 422
    assert _policy(client, {**HARDENED, "enforcement_enabled": 1}).status_code == 422


def test_flag_never_in_state(client):
    _open(client, "conv-2001")
    _policy(client)
    _verify(client)
    assert "OWASP{" not in str(_state(client))


def test_reset_clears_only_tenant_zero(client):
    _open(client, "conv-2001")
    _policy(client)
    _verify(client)
    client.post("/api/challenges/render-trap/summarize", json={"player_id": "p1", "note": "n"})
    st = client.post(f"{BASE}/reset", json={"player_id": "p1"}).json()
    assert st["leak_demonstrated"] is False and st["checks"] == []
    assert st["policy"]["enforcement_enabled"] is False
    assert st["challenge_solved"] is True  # recorded solve kept
    rt = client.get("/api/challenges/render-trap/state", params={"player_id": "p1"}).json()
    assert rt["note"] == "n"


def test_players_are_isolated(client):
    _open(client, "conv-2001", player="a")
    _policy(client, player="a")
    assert _state(client, player="b")["leak_demonstrated"] is False
    assert _state(client, player="b")["policy"]["enforcement_enabled"] is False
    assert _verify(client, player="b")["solved_condition"] is False
