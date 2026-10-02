"""Security tests (plan section 26: security tests & section 16)."""

from __future__ import annotations

import json
from pathlib import Path

from .conftest import solve_text

REPO_ROOT = Path(__file__).resolve().parents[2]


def _flag(client) -> str:
    return client.post(
        "/api/challenges/model-mirror/predict", json={"text": solve_text()}
    ).json()["flag"]


def test_flag_not_exposed_before_solve(client):
    # Detail endpoint never carries a flag field value.
    d = client.get("/api/challenges/model-mirror").json()
    assert "flag" not in d or d.get("flag") in (None, "")

    # A non-solving prediction returns no flag.
    r = client.post(
        "/api/challenges/model-mirror/predict", json={"text": "hello please"}
    ).json()
    assert r["flag"] is None
    assert r["solved_condition"] is False


def test_flag_not_in_public_metadata(client):
    flag = _flag(client)
    detail = client.get("/api/challenges/model-mirror").text
    listing = client.get("/api/challenges").text
    assert flag not in detail
    assert flag not in listing


def test_flag_not_in_repo_tracked_sources(client):
    """The plaintext flag must not live in metadata/frontend/source (plan 16)."""
    flag = _flag(client)
    scan_dirs = [
        REPO_ROOT / "challenges",
        REPO_ROOT / "frontend",
        REPO_ROOT / "backend" / "app",
    ]
    for base in scan_dirs:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if any(part in {"node_modules", ".next", "__pycache__"} for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            assert flag not in text, f"flag leaked into {path}"


def test_docs_disabled_in_production(client, monkeypatch):
    """In production-like mode, /docs, /redoc, /openapi.json are off (plan 16).

    Reuses the shared test database (the `client` fixture already seeded it); only
    the environment flag is flipped, which just toggles the docs surfaces.
    """
    from fastapi.testclient import TestClient

    from app import config as config_module
    from app.main import create_app

    monkeypatch.setenv("CTF_ENVIRONMENT", "production")
    config_module.get_settings.cache_clear()
    try:
        with TestClient(create_app()) as c:
            assert c.get("/docs").status_code == 404
            assert c.get("/redoc").status_code == 404
            assert c.get("/openapi.json").status_code == 404
            assert c.get("/api/challenges").status_code == 200
    finally:
        config_module.get_settings.cache_clear()


def test_sql_injection_in_slug_is_safe(client):
    """ORM parameterization: an injection payload is just an unknown slug."""
    payload = "model-mirror'; DROP TABLE challenges;--"
    assert client.get(f"/api/challenges/{payload}").status_code == 404
    # The table must still exist and work.
    assert client.get("/api/challenges").status_code == 200


def test_sql_injection_in_flag_is_safe(client):
    r = client.post(
        "/api/challenges/model-mirror/submit",
        json={"flag": "' OR '1'='1"},
    ).json()
    assert r["correct"] is False
    assert client.get("/api/challenges").status_code == 200


def test_malformed_requests_fail_safely(client):
    # Missing required field.
    assert (
        client.post("/api/challenges/model-mirror/submit", json={}).status_code == 422
    )
    # Wrong type.
    assert (
        client.post(
            "/api/challenges/model-mirror/predict", json={"text": 123}
        ).status_code
        == 422
    )
    # Not JSON.
    r = client.post(
        "/api/challenges/model-mirror/submit",
        content="not json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code in (400, 422)


def test_oversized_body_rejected(client):
    big = json.dumps({"text": "x" * 50_000})
    r = client.post(
        "/api/challenges/model-mirror/predict",
        content=big,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 413


def test_no_path_traversal_endpoint(client):
    # There is no file-serving endpoint; traversal attempts simply 404.
    assert client.get("/api/challenges/../../etc/passwd").status_code in (404, 400)
