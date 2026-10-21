"""Token Storm tests: simulator, solve validation, API, reset, isolation."""

from __future__ import annotations

import pytest

from app.challenges.token_storm import simulator as sim
from app.challenges.token_storm.simulator import Ledger, Policy
from app.services import flag_store

BASE = "/api/challenges/token-storm"
HARDENED = {
    "max_input_tokens": 1000,
    "max_output_tokens": 500,
    "max_requests": 10,
    "max_total_cost": 60,
    "enforcement_enabled": True,
}


@pytest.fixture(autouse=True)
def _fresh_limiter(client):
    from app.routes import token_storm as routes

    routes._rate_limiter.reset()


def _req(client, i, o, player="p1"):
    return client.post(f"{BASE}/request", json={"player_id": player, "input_tokens": i, "output_tokens": o})


def _policy(client, policy=HARDENED, player="p1"):
    return client.post(f"{BASE}/policy", json={"player_id": player, **policy})


def _verify(client, player="p1"):
    return client.post(f"{BASE}/verify", json={"player_id": player}).json()


def _state(client, player="p1"):
    return client.get(f"{BASE}/state", params={"player_id": player}).json()


def _abuse(client, player="p1"):
    return _req(client, *sim.LARGE_INPUT, player=player)


# --- simulator ---------------------------------------------------------------


def _enforced(**kw):
    return Policy(**{**HARDENED, **kw})


def test_cost_is_deterministic():
    assert sim.cost_of(200, 100) == 6
    assert sim.cost_of(6000, 100) == 64
    assert sim.cost_of(200, 3000) == 64
    assert sim.cost_of(0, 0) == 2


def test_normal_request_accepted():
    r = sim.process(Ledger(), _enforced(), *sim.NORMAL)
    assert r.accepted and r.message == "accepted: within policy" and r.cost == r.charged == 6


def test_input_and_output_caps():
    assert sim.process(Ledger(), _enforced(), *sim.LARGE_INPUT).message == "rejected: input limit exceeded"
    assert sim.process(Ledger(), _enforced(), *sim.LARGE_OUTPUT).message == "rejected: output cap exceeded"


def test_quota_blocks_repeats_and_rejections_are_free():
    led = Ledger()
    p = _enforced(max_requests=2)
    assert sim.process(led, p, *sim.NORMAL).accepted and sim.process(led, p, *sim.NORMAL).accepted
    before = led.remaining_budget
    assert sim.process(led, p, *sim.NORMAL).message == "rejected: quota exhausted"
    assert led.remaining_budget == before and led.request_count == 2


def test_budget_never_negative():
    led = Ledger(remaining_budget=5)
    r = sim.process(led, _enforced(max_input_tokens=100000, max_output_tokens=100000), *sim.NORMAL)
    assert not r.accepted and led.remaining_budget == 5
    r = sim.process(led, Policy(), *sim.LARGE_INPUT)  # unenforced overspend is clamped
    assert r.accepted and led.remaining_budget == 0 and r.charged == 5


@pytest.mark.parametrize("bad", [(-1, 0), (0, -1), (100001, 0), (1.5, 0), ("5", 0), (True, 0), (None, 0)])
def test_malformed_values_rejected(bad):
    with pytest.raises(ValueError):
        sim.process(Ledger(), Policy(), *bad)


def test_policy_validation():
    for bad in (0, -1, 100001, True, "5", 2.5):
        with pytest.raises(sim.PolicyInvalid):
            sim.validate_policy(Policy(max_input_tokens=bad))


def test_vulnerable_policy_fails_verification_hardened_passes():
    assert not all(c["passed"] for c in sim.verify_policy(sim.VULNERABLE_POLICY))
    assert all(c["passed"] for c in sim.verify_policy(_enforced()))


def test_verification_is_behavioural_not_a_single_config():
    for variant in (
        _enforced(max_input_tokens=5999, max_output_tokens=2999, max_requests=1000, max_total_cost=30),
        _enforced(max_input_tokens=300, max_output_tokens=150, max_requests=5, max_total_cost=100),
    ):
        assert all(c["passed"] for c in sim.verify_policy(variant))
    # limits that block abuse but also block normal use do not pass
    assert not all(c["passed"] for c in sim.verify_policy(_enforced(max_input_tokens=1)))
    # cosmetic: enforcement off with tight limits
    assert not all(c["passed"] for c in sim.verify_policy(_enforced(enforcement_enabled=False)))
    # quota too loose to cut the repeats off early
    assert not all(c["passed"] for c in sim.verify_policy(_enforced(max_requests=1000, max_total_cost=100)))


# --- API / solve validation ---------------------------------------------------


def test_listed_with_unique_identity(client):
    data = client.get("/api/challenges").json()
    assert [c["slug"] for c in data].count("token-storm") == 1
    ch = next(c for c in data if c["slug"] == "token-storm")
    assert ch["title"] == "Token Storm" and ch["category"] == "Unbounded Consumption"
    assert len(client.get("/api/challenges/token-storm").json()["hints"]) == 3
    for slug in ("model-mirror", "release-roulette", "render-trap", "model-crate",
                 "context-hijack", "trace-leak", "poisoned-memory"):
        assert slug in [c["slug"] for c in data]


def test_initial_state_is_vulnerable(client):
    st = _state(client)
    assert st["remaining_budget"] == 100 and st["policy"]["enforcement_enabled"] is False
    assert st["abuse_demonstrated"] is False and "OWASP{" not in str(st)


def test_abuse_reproduction_drains_budget(client):
    r = _abuse(client).json()
    assert r["result"]["accepted"] and r["result"]["cost"] == 64
    r = _abuse(client).json()
    assert r["state"]["remaining_budget"] == 0 and r["state"]["abuse_demonstrated"]
    assert len(r["state"]["history"]) == 2


def test_reproducing_abuse_alone_does_not_solve(client):
    _abuse(client)
    body = _verify(client)
    assert body["solved_condition"] is False and body["flag"] is None


def test_hardening_without_abuse_does_not_solve(client):
    _policy(client)
    body = _verify(client)
    assert all(c["passed"] for c in body["state"]["checks"])
    assert body["solved_condition"] is False and body["flag"] is None


def test_applying_limits_without_verifying_does_not_solve(client):
    _abuse(client)
    st = _policy(client).json()
    assert st["hardening_verified"] is False and st["challenge_solved"] is False


def test_blocking_without_normal_success_does_not_solve(client):
    _abuse(client)
    _policy(client, {**HARDENED, "max_input_tokens": 1, "max_output_tokens": 1})
    body = _verify(client)
    assert body["solved_condition"] is False
    assert not next(c for c in body["state"]["checks"] if "normal" in c["name"])["passed"]


def test_full_solve_and_flag_flow(client):
    _abuse(client)
    _policy(client)
    body = _verify(client)
    assert body["solved_condition"] is True
    assert body["flag"] == flag_store.load_flag("token-storm")
    assert body["state"]["analysis"]["owasp"] == "LLM10:2025"
    r = client.post(f"{BASE}/submit", json={"flag": body["flag"], "player_id": "p1"})
    assert r.json()["solved"] is True


def test_policy_change_voids_verification(client):
    _abuse(client)
    _policy(client)
    assert _verify(client)["state"]["hardening_verified"] is True
    st = _policy(client, {**HARDENED, "enforcement_enabled": False}).json()
    assert st["hardening_verified"] is False and st["checks"] == []


def test_client_cannot_fabricate_evidence(client):
    for extra in ({"solved": True}, {"isSolved": True}, {"abuse_demonstrated": True},
                  {"remaining_budget": 999}, {"cost": 0}, {"history": []}):
        assert client.post(f"{BASE}/request", json={"player_id": "p1", "input_tokens": 1, "output_tokens": 1, **extra}).status_code == 422
        assert client.post(f"{BASE}/verify", json={"player_id": "p1", **extra}).status_code == 422
        assert client.post(f"{BASE}/policy", json={"player_id": "p1", **HARDENED, **extra}).status_code == 422
    assert _state(client)["abuse_demonstrated"] is False


def test_api_validation(client):
    for i, o in ((-1, 0), (0, -1), (100001, 0), (1.5, 0), ("5", 0), (True, 0), (None, 0)):
        assert _req(client, i, o).status_code == 422
    assert _policy(client, {**HARDENED, "max_total_cost": 101}).status_code == 422
    assert _policy(client, {**HARDENED, "max_requests": 0}).status_code == 422
    assert _policy(client, {**HARDENED, "enforcement_enabled": "yes"}).status_code == 422
    assert _req(client, 1, 1, player="p" * 81).status_code == 422
    assert _state(client)["request_count"] == 0


def test_enforced_live_requests(client):
    _policy(client)
    assert _req(client, *sim.LARGE_INPUT).json()["result"]["message"] == "rejected: input limit exceeded"
    ok = _req(client, *sim.NORMAL).json()
    assert ok["result"]["accepted"] and ok["state"]["remaining_budget"] == 94


def test_flag_never_in_state(client):
    _abuse(client)
    _policy(client)
    _verify(client)
    assert "OWASP{" not in str(_state(client))


def test_reset_clears_only_token_storm(client):
    _abuse(client)
    _policy(client)
    _verify(client)
    client.post("/api/challenges/render-trap/summarize", json={"player_id": "p1", "note": "n"})
    st = client.post(f"{BASE}/reset", json={"player_id": "p1"}).json()
    assert st["remaining_budget"] == 100 and st["request_count"] == 0 and st["history"] == []
    assert st["policy"]["enforcement_enabled"] is False and st["abuse_demonstrated"] is False
    assert st["challenge_solved"] is True  # recorded solve kept
    rt = client.get("/api/challenges/render-trap/state", params={"player_id": "p1"}).json()
    assert rt["note"] == "n"


def test_players_are_isolated(client):
    _abuse(client, player="a")
    _policy(client, player="a")
    assert _state(client, player="b")["remaining_budget"] == 100
    assert _state(client, player="b")["policy"]["enforcement_enabled"] is False
    assert _verify(client, player="b")["solved_condition"] is False
