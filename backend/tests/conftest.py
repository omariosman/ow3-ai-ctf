"""Test fixtures.

All tests share one throwaway SQLite database (configured via env vars BEFORE
the app is imported, so every module binds to it). Each test gets a clean slate:
tables are dropped/recreated, the server-side flag store is wiped, and the
in-process oracle counters/rate limiter are reset.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# --- Configure the environment before importing any app module. ---
_TMP = Path(tempfile.mkdtemp(prefix="ctf-test-"))
os.environ["CTF_DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["CTF_ENVIRONMENT"] = "development"

from fastapi.testclient import TestClient  # noqa: E402

from app import database  # noqa: E402
from app.services import flag_store  # noqa: E402

# Isolate the flag store to the temp dir for the whole test session.
flag_store._FLAG_DIR = _TMP / "secrets"


def _reset_state() -> None:
    # Fresh schema + seed.
    database.Base.metadata.drop_all(bind=database.engine)
    # Wipe any previously generated flag so seeding creates a fresh one.
    if flag_store._FLAG_DIR.exists():
        for f in flag_store._FLAG_DIR.glob("*.flag"):
            f.unlink()
    database.init_db()

    # Reset in-process oracle state.
    from app.routes import predict as predict_routes

    predict_routes._request_counts.clear()
    predict_routes._rate_limiter.reset()


@pytest.fixture()
def client():
    _reset_state()
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def solve_text() -> str:
    """A documented input that lands BLOCK inside the solve band."""
    return "hello exploit hack"
