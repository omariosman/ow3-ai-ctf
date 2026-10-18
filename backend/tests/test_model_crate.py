"""Model Crate tests: verifier, state machine, API, and security."""

from __future__ import annotations

import ast
import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.challenges.model_crate import simulator as mc_sim
from app.challenges.model_crate import state as mc_state
from app.challenges.model_crate import verifier
from app.config import CHALLENGES_DIR, REPO_ROOT
from app.services import flag_store

BASE = "/api/challenges/model-crate"
APP_DIR = Path(__file__).resolve().parents[1] / "app"
MODULE_DIR = APP_DIR / "challenges" / "model_crate"
FIXTURE_SHA256 = "e5c9203eb3793cabb9af82461c596853bcf68d1bf0b5ce375ec49d7ec83e6727"
GENUINE_SHA256 = "0eceb6c4a1de871c013a2cd551101744fcf0a6562f25225c3d0b0cde0cc7c0cb"


@pytest.fixture(autouse=True)
def _fresh_limiter(client):
    from app.routes import model_crate as routes

    routes._rate_limiter.reset()


def _act(client, action, player="p1", **extra):
    return client.post(f"{BASE}/{action}", json={"player_id": player, **extra})


def _state(client, player="p1"):
    return client.get(f"{BASE}/state", params={"player_id": player}).json()


def _solve(client, player="p1"):
    assert _act(client, "inspect", player).status_code == 200
    assert _act(client, "compare", player).status_code == 200
    return _act(client, "quarantine", player)


def _artifact(data: bytes, **att) -> verifier.ReceivedArtifact:
    digest = verifier.sha256_hex(data)
    manifest = verifier.parse_manifest(
        {
            "name": "x",
            "version": "1.4.2",
            "artifact_id": "a.pkg",
            "publisher": "p",
            "claimed_sha256": digest,
            "attestation": {
                "signer": "northstar-release-2025",
                "source_repository": "git.northstar.example/ml/ticket-adapter",
                "signed_sha256": digest,
                "build_id": "b",
                **att,
            },
        }
    )
    return verifier.ReceivedArtifact("a.pkg", data, manifest)


# ------------------------------------------------------------------ verifier


def test_fixture_digest_is_deterministic_and_pinned():
    a = verifier.load_received_artifact()
    assert verifier.sha256_hex(a.data) == verifier.sha256_hex(a.data) == FIXTURE_SHA256


def test_expected_digest_comes_from_independent_trusted_record():
    trusted = verifier.load_trusted_release()
    received = verifier.load_received_artifact()
    assert trusted.expected_sha256 == GENUINE_SHA256
    assert trusted.expected_sha256 != verifier.sha256_hex(received.data)
    assert verifier._TRUSTED_PATH.parent != verifier._ARTIFACT_PATH.parent


def test_fixture_fails_closed_against_trusted_record():
    c = verifier.compare_digest(
        verifier.load_received_artifact(), verifier.load_trusted_release()
    )
    assert c.digest_match is False
    # The bundled manifest "claims" the right digest; that claim is not trusted.
    assert c.claimed_matches_trusted is True


def test_matching_bytes_pass_only_against_matching_trusted_digest():
    data = b"genuine bytes"
    art = _artifact(data)
    trusted = replace(verifier.load_trusted_release(), expected_sha256=verifier.sha256_hex(data))
    assert verifier.compare_digest(art, trusted).digest_match is True
    other = replace(trusted, expected_sha256=verifier.sha256_hex(b"other"))
    assert verifier.compare_digest(art, other).digest_match is False


def test_self_claimed_digest_is_never_the_reference():
    # Tampered bytes whose manifest claims their OWN digest still fail.
    art = _artifact(b"tampered")
    assert art.manifest.claimed_sha256 == verifier.sha256_hex(b"tampered")
    c = verifier.compare_digest(art, verifier.load_trusted_release())
    assert c.digest_match is False


def test_provenance_passes_only_when_every_check_passes():
    data = b"genuine bytes"
    trusted = replace(verifier.load_trusted_release(), expected_sha256=verifier.sha256_hex(data))
    assert verifier.verify_provenance(_artifact(data), trusted).verified is True


@pytest.mark.parametrize(
    "override",
    [
        {"signer": "unknown-key"},
        {"source_repository": "git.northstar-mirror.example/ml/ticket-adapter"},
        {"signed_sha256": "0" * 64},
        {"signer": ""},
    ],
)
def test_invalid_or_missing_provenance_fails(override):
    trusted = verifier.load_trusted_release()
    assert verifier.verify_provenance(_artifact(b"x", **override), trusted).verified is False


def test_fixture_provenance_fails_and_malformed_manifest_is_tolerated():
    r = verifier.verify_provenance(
        verifier.load_received_artifact(), verifier.load_trusted_release()
    )
    assert r.verified is False
    m = verifier.parse_manifest(["not", "a", "dict"])
    assert m.attestation.signer == "" and m.claimed_sha256 == ""
    assert len(verifier.parse_manifest({"name": "a" * 5000}).name) == 200


def test_is_verified_requires_digest_and_provenance():
    ok = verifier.Comparison("a", "a", "a", True, True)
    bad = verifier.Comparison("a", "b", "a", False, True)
    good_p = verifier.ProvenanceResult(True, ())
    assert verifier.is_verified(ok, good_p)
    assert not verifier.is_verified(ok, None)
    assert not verifier.is_verified(bad, good_p)


def test_simulator_is_deterministic_and_only_tampers_on_mismatch():
    assert mc_sim.simulate_load(False) == mc_sim.simulate_load(False)
    assert mc_sim.simulate_load(False).tampered is True
    assert mc_sim.simulate_load(True).tampered is False
    assert all(s.expected_route == s.actual_route for s in mc_sim.simulate_load(True).samples)


# --------------------------------------------------------------- state machine


def test_state_machine_happy_path_idempotency_and_reset(client):
    from app import database

    with database.SessionLocal() as db:
        assert mc_state.ensure_session(db, "p").status == mc_state.UNVERIFIED
        assert mc_state.inspect(db, "p")[1] is True
        assert mc_state.inspect(db, "p")[1] is False
        row, changed = mc_state.compare(db, "p")
        assert changed and row.status == mc_state.MISMATCH_CONFIRMED
        assert mc_state.compare(db, "p")[1] is False
        assert mc_state.quarantine(db, "p")[1] is True
        assert mc_state.quarantine(db, "p")[1] is False
        n = len(mc_state.audit_events(row))
        mc_state.inspect(db, "p")
        assert len(mc_state.audit_events(row)) == n  # no duplicate events
        row = mc_state.reset_player(db, "p")
        assert (row.status, row.digest_match, row.provenance_result, row.loaded) == (
            mc_state.UNVERIFIED, None, None, False,
        )
        assert mc_state.audit_events(row) == []


def test_invalid_transitions_raise(client):
    from app import database

    with database.SessionLocal() as db:
        for fn in (mc_state.compare, mc_state.check_provenance, mc_state.quarantine):
            with pytest.raises(mc_state.InvalidTransition):
                fn(db, "p")
        mc_state.inspect(db, "p")
        with pytest.raises(mc_state.InvalidTransition):
            mc_state.quarantine(db, "p")  # inspected only: no mismatch evidence


# ------------------------------------------------------------------------ API


def test_challenge_registered_with_metadata(client):
    items = client.get("/api/challenges").json()
    mc = next(c for c in items if c["slug"] == "model-crate")
    assert (mc["title"], mc["points"], mc["difficulty"]) == ("Model Crate", 175, "intermediate")
    detail = client.get("/api/challenges/model-crate").json()
    assert len(detail["hints"]) == 3
    assert "LLM03:2025" in (CHALLENGES_DIR / "model-crate" / "metadata.yaml").read_text()
    assert {c["slug"] for c in items} >= {"model-mirror", "release-roulette", "render-trap"}


def test_initial_state_hides_evidence(client):
    s = _state(client)
    assert s["status"] == "UNVERIFIED"
    assert s["artifact"] is None and s["comparison"] is None and s["provenance"] is None
    assert s["inventory"]["status"] == "UNVERIFIED"
    assert s["trusted_release"]["expected_sha256"] == GENUINE_SHA256
    assert FIXTURE_SHA256 not in json.dumps(s)  # actual digest appears only after inspect
    assert s["challenge_solved"] is False and s["analysis"] is None


def test_intended_path_solves_through_normal_flag_flow(client):
    r = _act(client, "inspect")
    assert r.json()["state"]["artifact"]["actual_sha256"] == FIXTURE_SHA256
    assert r.json()["flag"] is None
    c = _act(client, "compare").json()
    assert c["state"]["status"] == "MISMATCH_CONFIRMED"
    assert c["state"]["comparison"]["digest_match"] is False
    assert c["flag"] is None  # evidence alone does not reveal the flag
    q = _act(client, "quarantine").json()
    assert q["state"]["status"] == "QUARANTINED"
    assert "digest mismatch" in q["message"]
    assert q["flag"].startswith("OWASP{crate_")
    assert q["state"]["challenge_solved"] and q["state"]["analysis"]["owasp"] == "LLM03:2025"
    assert q["flag"] == flag_store.load_flag("model-crate")
    sub = client.post(
        "/api/challenges/model-crate/submit", json={"player_id": "p1", "flag": q["flag"]}
    ).json()
    assert sub["correct"] and sub["solved"]
    assert client.get("/api/challenges/model-crate", params={"player_id": "p1"}).json()["solved"]


def test_quarantine_is_idempotent_and_state_never_carries_flag(client):
    flag = _solve(client).json()["flag"]
    again = _act(client, "quarantine").json()
    assert again["changed"] is False and again["flag"] == flag
    assert flag not in json.dumps(_state(client))


@pytest.mark.parametrize("action", ["quarantine", "compare", "provenance"])
def test_shortcuts_without_evidence_are_rejected(client, action):
    r = _act(client, action)
    assert r.status_code == 409
    assert "flag" not in r.json() and _state(client)["status"] == "UNVERIFIED"
    assert client.get("/api/challenges/model-crate").json()["unlocked"] is False


def test_random_clicks_do_not_solve(client):
    for a in ("inspect", "provenance", "load", "inspect", "provenance"):
        assert _act(client, a).json()["flag"] is None
    assert _act(client, "quarantine").status_code == 409  # inspected, never compared
    assert _state(client)["challenge_solved"] is False


def test_provenance_alone_is_not_a_solve(client):
    _act(client, "inspect")
    r = _act(client, "provenance").json()
    assert r["state"]["provenance"]["verified"] is False
    assert r["state"]["provenance"]["simulated"] is True
    assert r["flag"] is None and r["state"]["status"] == "INSPECTED"


def test_load_before_verification_shows_consequence_but_does_not_solve(client):
    r = _act(client, "load").json()
    cons = r["state"]["consequence"]
    assert r["state"]["loaded"] and cons["tampered"] is True
    assert any(s["expected_route"] != s["actual_route"] for s in cons["samples"])
    assert r["flag"] is None and r["state"]["challenge_solved"] is False
    q = _solve(client).json()
    assert q["state"]["loaded"] is False and q["state"]["consequence"] is None


def test_failed_verification_blocks_load(client):
    _act(client, "inspect")
    _act(client, "compare")
    r = _act(client, "load")
    assert r.status_code == 409
    s = _state(client)
    assert s["loaded"] is False
    assert any(e["event"] == "load_blocked" for e in s["audit"])
    _act(client, "quarantine")
    assert _act(client, "load").status_code == 409


@pytest.mark.parametrize(
    "extra",
    [
        {"expected_sha256": "a" * 64},
        {"status": "QUARANTINED"},
        {"path": "/etc/passwd"},
        {"url": "http://evil.example/x"},
        {"package": "other"},
        {"solved": True},
    ],
)
def test_client_cannot_supply_digest_status_path_or_url(client, extra):
    for action in ("inspect", "compare", "provenance", "load", "quarantine", "reset"):
        assert _act(client, action, **extra).status_code == 422
    assert _state(client)["status"] == "UNVERIFIED"


def test_input_validation(client):
    assert client.post(f"{BASE}/inspect", json={"player_id": "x" * 81}).status_code == 422
    assert client.post(f"{BASE}/inspect", json=["bad"]).status_code == 422
    assert client.get(f"{BASE}/state", params={"player_id": "x" * 81}).status_code == 422


def test_sessions_are_isolated_per_player(client):
    _solve(client, "alice")
    assert _state(client, "bob")["status"] == "UNVERIFIED"
    assert _act(client, "quarantine", "bob").status_code == 409
    assert _state(client, "alice")["status"] == "QUARANTINED"


def test_reset_only_touches_model_crate_and_keeps_solve(client):
    flag = _solve(client).json()["flag"]
    client.post(
        "/api/challenges/model-crate/submit", json={"player_id": "p1", "flag": flag}
    )
    rt = client.post(
        "/api/challenges/render-trap/summarize", json={"player_id": "p1", "note": "hi"}
    ).json()
    s = client.post(f"{BASE}/reset", json={"player_id": "p1"}).json()
    assert s["status"] == "UNVERIFIED" and s["audit"] == [] and s["artifact"] is None
    assert client.get("/api/challenges/model-crate", params={"player_id": "p1"}).json()["solved"]
    after = client.get(
        "/api/challenges/render-trap/state", params={"player_id": "p1"}
    ).json()
    assert after["generation"] == rt["generation"]
    # After a reset the evidence path must be repeated to see the flag again.
    assert _act(client, "quarantine").status_code == 409


def test_reset_mid_interaction_restores_initial_state(client):
    _act(client, "inspect")
    _act(client, "load")
    s = client.post(f"{BASE}/reset", json={"player_id": "p1"}).json()
    assert (s["status"], s["loaded"], s["consequence"]) == ("UNVERIFIED", False, None)
    assert _act(client, "compare").status_code == 409


def test_rate_limited(client, monkeypatch):
    from app.rate_limit import SlidingWindowRateLimiter
    from app.routes import model_crate as routes

    monkeypatch.setattr(routes, "_rate_limiter", SlidingWindowRateLimiter(2, 60))
    assert _act(client, "inspect").status_code == 200
    assert _act(client, "inspect").status_code == 200
    assert _act(client, "inspect").status_code == 429


# ------------------------------------------------------------------- security


def test_no_dynamic_execution_in_module_or_routes():
    banned_calls = {"eval", "exec", "compile", "__import__", "system", "popen", "run", "Popen", "import_module"}
    banned_imports = {"subprocess", "importlib", "pickle", "marshal", "ctypes", "os", "socket", "urllib", "requests", "httpx"}
    for path in [*MODULE_DIR.glob("*.py"), APP_DIR / "routes" / "model_crate.py"]:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
                assert name not in banned_calls, f"{path.name}: {name}()"
            if isinstance(node, ast.Import):
                assert not {a.name.split(".")[0] for a in node.names} & banned_imports, path.name
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in banned_imports, path.name


def test_queries_are_orm_only():
    for path in [*MODULE_DIR.glob("*.py"), APP_DIR / "routes" / "model_crate.py"]:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
                assert name not in {"text", "execute", "exec_driver_sql"}, path.name
            if isinstance(node, ast.ImportFrom) and node.module == "sqlalchemy":
                assert "text" not in {a.name for a in node.names}, path.name


def test_fixture_is_inert_text_and_has_no_flag():
    fixtures = MODULE_DIR / "fixtures"
    for path in fixtures.rglob("*"):
        if not path.is_file() or path.name == ".gitattributes":
            continue
        raw = path.read_bytes()
        assert b"\x00" not in raw and not raw.startswith((b"#!", b"MZ", b"\x7fELF")), path
        text = raw.decode("utf-8")
        assert "OWASP{" not in text, path
    for meta in (CHALLENGES_DIR / "model-crate").glob("*.yaml"):
        assert "OWASP{" not in meta.read_text()


def test_flag_absent_from_public_surfaces_before_solve(client):
    flag = flag_store.load_flag("model-crate")
    assert flag
    blobs = [
        json.dumps(client.get("/api/challenges").json()),
        json.dumps(client.get("/api/challenges/model-crate").json()),
        json.dumps(_state(client)),
        json.dumps(_act(client, "inspect").json()),
        json.dumps(_act(client, "compare").json()),
    ]
    assert all(flag not in b for b in blobs)


def test_no_host_paths_or_env_leaked(client):
    _act(client, "inspect")
    _act(client, "compare")
    _act(client, "provenance")
    body = json.dumps(_state(client))
    assert str(REPO_ROOT) not in body and "/home/" not in body and "CTF_" not in body
    err = _act(client, "load").text
    assert "Traceback" not in err and str(REPO_ROOT) not in err


def test_artifact_never_reaches_a_loader():
    # The only thing done with the artifact is reading bytes and hashing them.
    src = (MODULE_DIR / "verifier.py").read_text()
    assert "read_bytes()" in src and "hashlib.sha256" in src
    for word in ("pickle", "torch", "joblib", "import_module", "load_model"):
        assert word not in src
