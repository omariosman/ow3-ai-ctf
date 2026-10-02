#!/usr/bin/env python3
"""Reset all local progress (plan section 32).

Drops every table, deletes the server-side flag store (so a fresh flag is
generated), then re-initializes and re-seeds. This wipes players, submissions,
solves, and progress.

Usage:
    PYTHONPATH=backend python scripts/reset_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.database import Base, engine, init_db  # noqa: E402
from app.services import flag_store  # noqa: E402


def main() -> None:
    Base.metadata.drop_all(bind=engine)
    print("Dropped all tables.")

    if flag_store._FLAG_DIR.exists():
        for f in flag_store._FLAG_DIR.glob("*.flag"):
            f.unlink()
            print(f"Removed flag file: {f.name}")

    init_db()
    print("Re-initialized and re-seeded. Local progress has been reset.")


if __name__ == "__main__":
    main()
