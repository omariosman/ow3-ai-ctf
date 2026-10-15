"""Platform-level tests (plan section 26: backend tests)."""

from __future__ import annotations

from .conftest import solve_text


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_challenge_listing(client):
    r = client.get("/api/challenges")
    assert r.status_code == 200
    data = {c["slug"]: c for c in r.json()}
    assert "model-mirror" in data
    assert data["model-mirror"]["points"] == 100
    assert data["model-mirror"]["solved"] is False


def test_challenge_lookup(client):
    r = client.get("/api/challenges/model-mirror")
    assert r.status_code == 200
    d = r.json()
    assert d["title"] == "Model Mirror"
    assert len(d["hints"]) == 3
    assert d["unlocked"] is False
    assert d["solved"] is False


def test_unknown_challenge_404(client):
    assert client.get("/api/challenges/does-not-exist").status_code == 404
    r = client.post(
        "/api/challenges/does-not-exist/submit", json={"flag": "OWASP{x}"}
    )
    assert r.status_code == 404


def _get_flag(client) -> str:
    r = client.post(
        "/api/challenges/model-mirror/predict", json={"text": solve_text()}
    ).json()
    assert r["solved_condition"] is True
    assert r["flag"]
    return r["flag"]


def test_valid_flag_solves(client):
    flag = _get_flag(client)
    r = client.post("/api/challenges/model-mirror/submit", json={"flag": flag}).json()
    assert r["correct"] is True
    assert r["solved"] is True


def test_invalid_flag_rejected(client):
    r = client.post(
        "/api/challenges/model-mirror/submit", json={"flag": "OWASP{mirror_deadbeef}"}
    ).json()
    assert r["correct"] is False
    assert r["solved"] is False


def test_duplicate_solve_handled(client):
    flag = _get_flag(client)
    client.post("/api/challenges/model-mirror/submit", json={"flag": flag})
    r = client.post("/api/challenges/model-mirror/submit", json={"flag": flag}).json()
    assert r["correct"] is True
    assert r["solved"] is True
    assert "already" in r["message"].lower()

    # Still exactly one solve recorded -> reflected in the listing.
    listing = client.get("/api/challenges").json()
    assert listing[0]["solved"] is True


def test_solve_persists_in_detail(client):
    flag = _get_flag(client)
    client.post("/api/challenges/model-mirror/submit", json={"flag": flag})
    d = client.get("/api/challenges/model-mirror").json()
    assert d["solved"] is True
    assert d["unlocked"] is True
