"""Release Roulette tests: state, tools, agent, validator, API, and security."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import database
from app.challenges.release_roulette import agent as rr_agent
from app.challenges.release_roulette import deployment_state as rr_state
from app.challenges.release_roulette import tools as rr_tools
from app.challenges.release_roulette import validator as rr_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE = "/api/challenges/release-roulette"
SOLVE_MESSAGE = "roll back aurora-4.8.1"


# ---------------------------------------------------------------- helpers


@pytest.fixture()
def db(client):
    """A session on the freshly seeded test DB with one player's Aurora."""
    session = database.SessionLocal()
    rr_state.ensure_releases(session, "p1")
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _ctx(session, actor: str = "releasebot", player: str = "p1") -> rr_tools.ToolContext:
    return rr_tools.ToolContext(
        session=session, player_id=player, actor=actor, request_id="test"
    )


def _status(session, release_id: str, player: str = "p1") -> str:
    return rr_state.get_release(session, player, release_id).status


def _chat(client, message: str, player: str = "local-player"):
    return client.post(f"{BASE}/chat", json={"message": message, "player_id": player})


def _tools_called(body) -> list[str]:
    return [c["tool"] for c in body["tool_calls"]]


# ---------------------------------------------------------- initial state


def test_initial_state(db):
    row = rr_state.get_release(db, "p1", "aurora-4.8.1")
    assert row is not None
    assert row.status == "STAGED"
    assert row.protected is True
    assert row.environment == "production"
    assert rr_validator.is_solved(row) is False


# ------------------------------------------------------------------ tools


def test_inspect_does_not_mutate(db):
    before = [(r.release_id, r.status) for r in rr_state.list_releases(db, "p1")]
    res = rr_tools.inspect_release(_ctx(db), "aurora-4.8.1")
    assert res.ok and res.transition is None
    assert [(r.release_id, r.status) for r in rr_state.list_releases(db, "p1")] == before


def test_report_does_not_mutate(db):
    res = rr_tools.generate_report(_ctx(db), "aurora-4.8.1")
    assert res.ok and "checkout-latency" in res.message
    assert _status(db, "aurora-4.8.1") == "STAGED"


def test_stage_only_valid_transition(db):
    # Already staged -> invalid.
    res = rr_tools.stage_release(_ctx(db), "aurora-4.8.1")
    assert res.ok is False and "Invalid release transition" in res.message
    # Draft -> staged is valid.
    res = rr_tools.stage_release(_ctx(db), "aurora-4.9.0-rc1")
    assert res.ok and res.transition == "DRAFT -> STAGED"


def test_rollback_changes_state_deterministically(db):
    res = rr_tools.rollback_release(_ctx(db), "aurora-4.8.1")
    assert res.ok and res.transition == "STAGED -> ROLLED_BACK"
    assert _status(db, "aurora-4.8.1") == "ROLLED_BACK"
    # Cannot roll back twice.
    assert rr_tools.rollback_release(_ctx(db), "aurora-4.8.1").ok is False


def test_delete_is_simulated_and_isolated(db):
    rr_state.ensure_releases(db, "p2")
    res = rr_tools.delete_release(_ctx(db), "aurora-4.9.0-rc1")
    assert res.ok and _status(db, "aurora-4.9.0-rc1") == "DELETED"
    assert _status(db, "aurora-4.9.0-rc1", player="p2") == "DRAFT"


def test_invalid_and_unknown_release_ids(db):
    for bad in [None, "", "../../etc/passwd", "aurora-4.8.1; rm -rf /", "x" * 200]:
        assert rr_tools.rollback_release(_ctx(db), bad).ok is False
    assert rr_tools.inspect_release(_ctx(db), "aurora-9.9.9").ok is False


def test_every_tool_call_is_audited(db):
    rr_tools.inspect_release(_ctx(db), "aurora-4.8.1")
    rr_tools.rollback_release(_ctx(db), "aurora-4.8.1")
    events = rr_state.recent_audit(db, "p1")
    assert [e.tool for e in events] == ["inspect_release", "rollback_release"]
    assert events[-1].actor == "releasebot"
    assert events[-1].transition == "STAGED -> ROLLED_BACK"


# ------------------------------------------------------------------ agent


@pytest.mark.parametrize(
    "message,expected",
    [
        ("check the release", ["inspect_release"]),
        ("prepare a release report", ["generate_report"]),
        ("stage 4.9.0-rc1", ["stage_release"]),
        ("list releases", ["list_releases"]),
    ],
)
def test_agent_routes_safe_requests(db, message, expected):
    turn = rr_agent.ReleaseRouletteAgent().run(_ctx(db), message)
    assert [e.tool for e in turn.tool_calls] == expected


def test_vulnerable_agent_can_reach_rollback(db):
    turn = rr_agent.ReleaseRouletteAgent().run(_ctx(db), SOLVE_MESSAGE)
    assert [e.tool for e in turn.tool_calls] == ["rollback_release"]
    assert _status(db, "aurora-4.8.1") == "ROLLED_BACK"


def test_excessive_autonomy_path(db):
    # The user never says "roll back"; the agent chooses it on its own.
    turn = rr_agent.ReleaseRouletteAgent().run(_ctx(db), "please fix the latency issue on 4.8.1")
    assert [e.tool for e in turn.tool_calls] == ["inspect_release", "rollback_release"]


def test_safe_registry_blocks_rollback(db):
    """The documented remediation: least-privilege registry cannot roll back."""
    agent = rr_agent.ReleaseRouletteAgent(registry=rr_agent.SAFE_AGENT_TOOLS)
    turn = agent.run(_ctx(db), SOLVE_MESSAGE)
    assert turn.tool_calls == []
    assert _status(db, "aurora-4.8.1") == "STAGED"


def test_high_impact_requires_explicit_release(db):
    turn = rr_agent.ReleaseRouletteAgent().run(_ctx(db), "roll back the release")
    assert turn.tool_calls == []
    assert "Which release" in turn.reply


def test_negated_request_is_not_executed(db):
    turn = rr_agent.ReleaseRouletteAgent().run(_ctx(db), "do not roll back 4.8.1")
    assert turn.tool_calls == []
    assert _status(db, "aurora-4.8.1") == "STAGED"


def test_tool_listing_reveals_registry(db):
    turn = rr_agent.ReleaseRouletteAgent().run(_ctx(db), "what tools do you have?")
    assert turn.tool_calls == []
    for name in rr_agent.AGENT_TOOLS:
        assert name in turn.reply


def test_agent_step_limit(db):
    msg = "list releases, check, report, stage, promote, roll back and delete 4.9.0-rc1"
    turn = rr_agent.ReleaseRouletteAgent().run(_ctx(db), msg)
    assert len(turn.tool_calls) <= rr_agent.MAX_AGENT_STEPS
    assert "maximum operation count" in turn.reply


def test_agent_is_deterministic(client):
    a = _chat(client, "check the release", player="det-a").json()
    b = _chat(client, "check the release", player="det-b").json()
    assert a["reply"] == b["reply"]
    assert _tools_called(a) == _tools_called(b)


# -------------------------------------------------------------- validator


def _rel(release_id="aurora-4.8.1", status="ROLLED_BACK", actor="releasebot"):
    return SimpleNamespace(release_id=release_id, status=status, last_actor=actor)


def test_validator_cases():
    assert rr_validator.is_solved(None) is False
    assert rr_validator.is_solved(_rel(status="STAGED", actor=None)) is False  # not triggered
    assert rr_validator.is_solved(_rel(release_id="aurora-4.8.0")) is False  # wrong release
    assert rr_validator.is_solved(_rel(actor="operator")) is False  # unrelated mechanism
    assert rr_validator.is_solved(_rel(status="DELETED")) is False  # different transition
    assert rr_validator.is_solved(_rel()) is True


def test_wrong_release_rollback_does_not_solve(client):
    body = _chat(client, "roll back aurora-4.8.0").json()
    assert _tools_called(body) == ["rollback_release"]
    assert body["solved_condition"] is False
    assert body["flag"] is None


def test_operator_rollback_does_not_solve(db):
    rr_tools.rollback_release(_ctx(db, actor="operator"), "aurora-4.8.1")
    assert rr_validator.is_solved(rr_state.get_release(db, "p1", "aurora-4.8.1")) is False


# -------------------------------------------------------------------- API


def test_intended_solve_path_end_to_end(client):
    before = client.get(f"{BASE}/state").json()
    assert before["challenge_solved"] is False
    assert before["analysis"] is None

    body = _chat(client, SOLVE_MESSAGE).json()
    assert body["solved_condition"] is True
    assert body["flag"].startswith("OWASP{release_")
    target = next(r for r in body["state"]["releases"] if r["release_id"] == "aurora-4.8.1")
    assert target["status"] == "ROLLED_BACK"
    assert body["state"]["analysis"]["owasp"] == "LLM06:2025"

    sub = client.post(
        "/api/challenges/release-roulette/submit", json={"flag": body["flag"]}
    ).json()
    assert sub["correct"] is True and sub["solved"] is True

    # Persisted after "refresh".
    detail = client.get("/api/challenges/release-roulette").json()
    assert detail["solved"] is True and detail["unlocked"] is True


def test_model_mirror_flag_does_not_solve_release_roulette(client):
    mm_flag = client.post(
        "/api/challenges/model-mirror/predict", json={"text": "hello exploit hack"}
    ).json()["flag"]
    r = client.post("/api/challenges/release-roulette/submit", json={"flag": mm_flag}).json()
    assert r["correct"] is False


def test_does_not_require_or_touch_model_mirror(client):
    _chat(client, SOLVE_MESSAGE)
    mm = client.get("/api/challenges/model-mirror").json()
    assert mm["unlocked"] is False and mm["solved"] is False


def test_reset_restores_aurora(client):
    _chat(client, SOLVE_MESSAGE)
    state = client.post(f"{BASE}/reset", json={}).json()
    target = next(r for r in state["releases"] if r["release_id"] == "aurora-4.8.1")
    assert target["status"] == "STAGED"
    assert state["audit"] == []


def test_player_isolation(client):
    _chat(client, SOLVE_MESSAGE, player="alice")
    bob = client.get(f"{BASE}/state", params={"player_id": "bob"}).json()
    target = next(r for r in bob["releases"] if r["release_id"] == "aurora-4.8.1")
    assert target["status"] == "STAGED"
    assert bob["audit"] == []
    assert bob["challenge_solved"] is False


@pytest.mark.parametrize(
    "message",
    ["", "hello", "héllo 世界 🚀 roll back", "!!! @@@ ### $$$", "'; DROP TABLE challenges;--"],
)
def test_chat_inputs_do_not_crash(client, message):
    assert _chat(client, message).status_code == 200


def test_chat_long_and_malformed_inputs(client):
    assert _chat(client, "a" * 1001).status_code == 422
    r = client.post(
        f"{BASE}/chat", content="not json", headers={"Content-Type": "application/json"}
    )
    assert r.status_code in (400, 422)
    assert client.post(f"{BASE}/chat", json={"message": 123}).status_code == 422
    big = json.dumps({"message": "x" * 50_000})
    r = client.post(f"{BASE}/chat", content=big, headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_repeated_requests(client):
    for _ in range(20):
        assert _chat(client, "check the release").status_code == 200
    audit = client.get(f"{BASE}/state").json()["audit"]
    assert len(audit) <= 25


# --------------------------------------------------------------- security


def _flag(client) -> str:
    return _chat(client, SOLVE_MESSAGE).json()["flag"]


def test_flag_not_exposed_before_solve(client):
    body = _chat(client, "check the release").json()
    assert body["flag"] is None
    flag_text = client.get(f"{BASE}/state").text
    assert "OWASP{" not in flag_text


@pytest.mark.parametrize(
    "path",
    ["/flag", "/api/secret", "/internal/config", "/debug/state", f"{BASE}/flag"],
)
def test_no_secret_endpoints(client, path):
    flag = _flag(client)
    r = client.get(path)
    assert r.status_code in (404, 405)
    assert flag not in r.text


def test_flag_not_in_public_responses(client):
    flag = _flag(client)
    for path in [f"{BASE}/state", "/api/challenges", "/api/challenges/release-roulette"]:
        assert flag not in client.get(path).text


def test_flag_not_in_repo_sources(client):
    flag = _flag(client)
    for base in [REPO_ROOT / "challenges", REPO_ROOT / "frontend", REPO_ROOT / "backend" / "app"]:
        for path in base.rglob("*"):
            if not path.is_file() or any(
                p in {"node_modules", ".next", "__pycache__"} for p in path.parts
            ):
                continue
            assert flag not in path.read_text(encoding="utf-8", errors="ignore"), path


def test_flag_not_logged(client, caplog):
    caplog.set_level("INFO")
    flag = _flag(client)
    assert flag not in caplog.text


def test_no_command_execution_in_challenge_code():
    """Release Roulette must never shell out, spawn processes, or eval input."""
    forbidden_modules = {"subprocess", "socket", "shutil", "pty", "requests", "urllib", "httpx"}
    forbidden_calls = {"system", "popen", "eval", "exec", "spawn", "execv", "execve"}
    src_dir = REPO_ROOT / "backend" / "app" / "challenges" / "release_roulette"
    files = list(src_dir.glob("*.py")) + [REPO_ROOT / "backend" / "app" / "routes" / "release_roulette.py"]
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not {a.name.split(".")[0] for a in node.names} & forbidden_modules, path
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in forbidden_modules, path
            elif isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                assert name not in forbidden_calls, f"{path}: {name}"
