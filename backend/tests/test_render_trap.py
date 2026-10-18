"""RenderTrap tests: simulator, state/proof validation, API, and security."""

from __future__ import annotations

import ast
import re
from datetime import timedelta
from pathlib import Path

import pytest

from app import database
from app.challenges.render_trap import preview as rt_preview
from app.challenges.render_trap import simulator as rt_sim
from app.challenges.render_trap import state as rt_state
from app.services import flag_store

BASE = "/api/challenges/render-trap"
XSS = '<img src=x onerror="rtPreview.confirm()">'
APP_DIR = Path(__file__).resolve().parents[1] / "app"


@pytest.fixture(autouse=True)
def _fresh_limiter(client):
    from app.routes import render_trap as routes

    routes._rate_limiter.reset()


def _submit(client, note="", player="p1"):
    return client.post(f"{BASE}/summarize", json={"player_id": player, "note": note})


def _proof(client, state, player="p1", **over):
    body = {
        "player_id": player,
        "event": "render_execution_confirmed",
        "generation": state["generation"],
        "nonce": _nonce(state),
    }
    body.update(over)
    return client.post(f"{BASE}/proof", json=body)


def _nonce(state) -> str:
    return re.search(r'"nonce": "([^"]+)"', state["preview_html"]).group(1)


# ---------------------------------------------------------------- simulator


def test_simulator_is_deterministic():
    assert rt_sim.generate_summary("hello") == rt_sim.generate_summary("hello")
    assert "hello" in rt_sim.generate_summary("hello")


def test_simulator_empty_and_whitespace():
    for v in ("", "   ", None):
        assert "No agent note provided." in rt_sim.generate_summary(v)


def test_simulator_overlong_rejected():
    with pytest.raises(rt_sim.NoteTooLong):
        rt_sim.generate_summary("a" * (rt_sim.MAX_NOTE_LENGTH + 1))
    rt_sim.generate_summary("a" * rt_sim.MAX_NOTE_LENGTH)


def test_simulator_keeps_html_as_data_and_strips_control_chars():
    out = rt_sim.generate_summary("<b>x</b>\x00\x07")
    assert "<b>x</b>" in out
    assert "\x00" not in out and "\x07" not in out


# ------------------------------------------------------------------- state


@pytest.fixture()
def db(client):
    session = database.SessionLocal()
    from app.services import progress

    progress.ensure_player(session, "p1")
    progress.ensure_player(session, "p2")
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_proof_rejects_without_session(db):
    ok, reason = rt_state.validate_proof(db, "p1", generation=1, nonce="x")
    assert not ok and reason == rt_state.REJECT_NO_SESSION


def test_proof_wrong_nonce_and_generation_rejected(db):
    row = rt_state.submit_note(db, "p1", XSS)
    assert not rt_state.validate_proof(db, "p1", generation=row.generation, nonce="bad")[0]
    assert not rt_state.validate_proof(
        db, "p1", generation=row.generation + 1, nonce=row.nonce
    )[0]
    assert rt_state.validate_proof(db, "p1", generation=row.generation, nonce=row.nonce)[0]


def test_proof_is_one_time(db):
    row = rt_state.submit_note(db, "p1", XSS)
    n, g = row.nonce, row.generation
    assert rt_state.validate_proof(db, "p1", generation=g, nonce=n)[0]
    assert not rt_state.validate_proof(db, "p1", generation=g, nonce=n)[0]


def test_proof_expired(db):
    row = rt_state.submit_note(db, "p1", XSS)
    row.nonce_expires_at = row.nonce_expires_at - rt_state.NONCE_TTL - timedelta(seconds=1)
    db.flush()
    ok, reason = rt_state.validate_proof(db, "p1", generation=row.generation, nonce=row.nonce)
    assert not ok and reason == rt_state.REJECT_EXPIRED


def test_proof_requires_markup_in_output(db):
    row = rt_state.submit_note(db, "p1", "ok")
    row.raw_output = "plain text only"  # no tags at all
    ok, reason = rt_state.validate_proof(db, "p1", generation=row.generation, nonce=row.nonce)
    assert not ok and reason == rt_state.REJECT_NOT_MARKUP


def test_other_players_nonce_rejected(db):
    a = rt_state.submit_note(db, "p1", XSS)
    b = rt_state.submit_note(db, "p2", XSS)
    assert not rt_state.validate_proof(db, "p2", generation=b.generation, nonce=a.nonce)[0]


def test_reset_invalidates_old_proof(db):
    row = rt_state.submit_note(db, "p1", XSS)
    n, g = row.nonce, row.generation
    rt_state.reset_player(db, "p1")
    assert not rt_state.validate_proof(db, "p1", generation=g, nonce=n)[0]
    fresh = rt_state.get_session(db, "p1")
    assert fresh.generation > g and fresh.raw_output is None


# --------------------------------------------------------------------- API


def test_registry_listing(client):
    data = {c["slug"]: c for c in client.get("/api/challenges").json()}
    assert {"model-mirror", "release-roulette", "render-trap"} <= set(data)
    rt = data["render-trap"]
    assert rt["points"] == 150 and rt["solved"] is False
    assert rt["category"] == "Improper Output Handling"
    d = client.get("/api/challenges/render-trap").json()
    assert len(d["hints"]) == 3 and d["unlocked"] is False


def test_state_before_submit(client):
    s = client.get(f"{BASE}/state", params={"player_id": "p1"}).json()
    assert s["raw_output"] is None and s["preview_html"] is None
    assert s["ticket"]["id"] == "NST-2048" and s["status"] == "active"


def test_normal_interaction_does_not_solve(client):
    for note in ("", "please check the plan", "script", "<script> is mentioned"):
        s = _submit(client, note).json()
    assert s["challenge_solved"] is False
    assert client.get("/api/challenges/render-trap").json()["unlocked"] is False


def test_submit_validation(client):
    assert _submit(client, "a" * 1001).status_code == 422
    r = client.post(f"{BASE}/summarize", json={"player_id": "p1", "note": 5})
    assert r.status_code == 422
    r = client.post(f"{BASE}/summarize", json={"player_id": "p1", "extra": 1})
    assert r.status_code == 422
    r = client.post(f"{BASE}/summarize", content="not json",
                    headers={"Content-Type": "text/plain"})
    assert r.status_code == 422


def test_intended_solve_flow(client):
    s = _submit(client, XSS).json()
    assert XSS in s["raw_output"]
    r = _proof(client, s)
    body = r.json()
    assert r.status_code == 200 and body["accepted"] is True
    assert body["flag"] == flag_store.load_flag("render-trap")
    assert body["state"]["challenge_solved"] is True
    # Platform submit flow records the solve.
    sub = client.post("/api/challenges/render-trap/submit",
                      json={"player_id": "p1", "flag": body["flag"]})
    assert sub.json()["solved"] is True
    assert client.get("/api/challenges/render-trap", params={"player_id": "p1"}).json()["solved"] is True


def test_duplicate_event_rejected_and_no_second_flag(client):
    s = _submit(client, XSS).json()
    assert _proof(client, s).json()["accepted"] is True
    again = _proof(client, s).json()
    assert again["accepted"] is False and again["flag"] is None


def test_stale_generation_after_resubmit_rejected(client):
    old = _submit(client, XSS).json()
    _submit(client, XSS)
    r = _proof(client, old).json()
    assert r["accepted"] is False and r["flag"] is None


def test_stale_frame_after_reset_rejected(client):
    old = _submit(client, XSS).json()
    client.post(f"{BASE}/reset", json={"player_id": "p1"})
    r = _proof(client, old).json()
    assert r["accepted"] is False and r["flag"] is None


def test_other_player_cannot_solve(client):
    s = _submit(client, XSS, player="p1").json()
    _submit(client, XSS, player="p2")
    r = _proof(client, s, player="p2").json()
    assert r["accepted"] is False and r["flag"] is None
    assert client.get("/api/challenges/render-trap",
                      params={"player_id": "p2"}).json()["unlocked"] is False


def test_proof_schema_is_strict(client):
    s = _submit(client, XSS).json()
    assert _proof(client, s, event="other").status_code == 422
    assert _proof(client, s, extra="x").status_code == 422
    assert _proof(client, s, generation="1").status_code == 422
    assert _proof(client, s, nonce="").status_code == 422
    r = client.post(f"{BASE}/proof", json={"player_id": "p1"})
    assert r.status_code == 422


def test_plain_output_cannot_be_proven(client, db):
    s = _submit(client, "hello").json()
    # The default summary has formatting tags, so force a markup-free output.
    row = rt_state.get_session(db, "p1")
    row.raw_output = "no tags"
    db.commit()
    r = _proof(client, s).json()
    assert r["accepted"] is False


def test_reset_only_affects_render_trap(client):
    s = _submit(client, XSS).json()
    assert _proof(client, s).json()["accepted"] is True
    client.post("/api/challenges/release-roulette/chat",
                json={"player_id": "p1", "message": "list releases"})
    client.post(f"{BASE}/reset", json={"player_id": "p1"})
    rr = client.get("/api/challenges/release-roulette/state", params={"player_id": "p1"}).json()
    assert len(rr["releases"]) == 3 and len(rr["audit"]) >= 1
    st = client.get(f"{BASE}/state", params={"player_id": "p1"}).json()
    assert st["raw_output"] is None and st["challenge_solved"] is True  # solve untouched


def test_unknown_player_id_too_long(client):
    assert client.get(f"{BASE}/state", params={"player_id": "x" * 81}).status_code == 422


def test_rate_limit(client):
    from app.routes import render_trap as routes

    routes._rate_limiter.max_requests = 2
    try:
        assert _submit(client).status_code == 200
        assert _submit(client).status_code == 200
        assert _submit(client).status_code == 429
    finally:
        routes._rate_limiter.max_requests = 120


# ---------------------------------------------------------------- security


def test_flag_absent_from_state_output_preview_and_metadata(client):
    flag = flag_store.load_flag("render-trap")
    s = _submit(client, XSS).json()
    blob = client.get(f"{BASE}/state", params={"player_id": "p1"}).text
    assert flag not in blob and flag not in str(s)
    assert flag not in client.get("/api/challenges/render-trap").text
    assert flag not in client.get("/api/challenges").text
    assert flag not in s["preview_html"] and flag not in s["raw_output"]
    # Rejected proofs do not leak it either.
    bad = client.post(f"{BASE}/proof", json={
        "player_id": "p1", "event": "render_execution_confirmed",
        "generation": 999, "nonce": "nope"})
    assert flag not in bad.text


def test_flag_absent_from_source_and_frontend():
    flag = flag_store.load_flag("render-trap")  # may be None in a clean env
    repo = APP_DIR.parents[1]
    paths = [p for root in (repo / "challenges" / "render-trap", repo / "frontend" / "app",
                            repo / "frontend" / "components", repo / "frontend" / "lib",
                            APP_DIR / "challenges" / "render_trap")
             for p in root.rglob("*") if p.is_file() and "node_modules" not in p.parts]
    assert paths
    for p in paths:
        text = p.read_text(encoding="utf-8", errors="ignore")
        if flag:
            assert flag not in text, p
        assert not re.search(r"OWASP\{render_[0-9a-f]{16}\}", text), p


def test_preview_document_is_contained():
    doc = rt_preview.build_preview_document("<p>x</p>", generation=3, nonce="abc")
    assert "default-src 'none'" in doc and "connect-src 'none'" in doc
    assert "form-action 'none'" in doc and "base-uri 'none'" in doc
    # The only parent-facing call is the one fixed-shape proof message.
    assert doc.count("parent.postMessage") == 1
    for banned in ("fetch(", "XMLHttpRequest", "localStorage", "document.cookie",
                   "window.top", "eval("):
        assert banned not in doc
    assert '"generation": 3' in doc and '"nonce": "abc"' in doc


def test_unsafe_sink_confined_to_preview_module():
    """The intentional unescaped sink exists only in preview.py; no shared UI
    component, backend route or main-origin page uses an HTML sink."""
    repo = APP_DIR.parents[1]
    for p in (repo / "frontend").rglob("*.tsx"):
        if "node_modules" in p.parts:
            continue
        assert "dangerouslySetInnerHTML" not in p.read_text(), p
        assert "innerHTML" not in p.read_text(), p


def test_frontend_iframe_sandbox_flags():
    repo = APP_DIR.parents[1]
    src = (repo / "frontend" / "components" / "render-trap-preview.tsx").read_text()
    m = re.search(r'sandbox="([^"]*)"', src)
    assert m and m.group(1).split() == ["allow-scripts"]
    assert "allow-same-origin" not in src
    assert "event.source" in src and "contentWindow" in src


def test_no_dynamic_execution_added():
    """No eval/exec/shell/dynamic import in the RenderTrap backend code."""
    files = list((APP_DIR / "challenges" / "render_trap").glob("*.py")) + [
        APP_DIR / "routes" / "render_trap.py"]
    banned_names = {"eval", "exec", "compile", "__import__"}
    banned_attrs = {"system", "popen", "run", "Popen", "import_module"}
    banned_imports = {"subprocess", "os", "importlib", "ctypes"}
    for f in files:
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name):
                    assert fn.id not in banned_names, (f, fn.id)
                elif isinstance(fn, ast.Attribute):
                    assert fn.attr not in banned_attrs, (f, fn.attr)
            if isinstance(node, ast.Import):
                assert not ({a.name.split(".")[0] for a in node.names} & banned_imports), f
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in banned_imports, f


def test_works_without_network_or_keys():
    for f in list((APP_DIR / "challenges" / "render_trap").glob("*.py")):
        t = f.read_text()
        assert "requests" not in t and "httpx" not in t and "urllib" not in t
        assert "API_KEY" not in t
