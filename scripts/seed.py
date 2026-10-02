#!/usr/bin/env python3
"""Initialize the database and seed challenges (plan section 8).

Usage:
    cd backend && python ../scripts/seed.py
    # or from repo root with backend deps available:
    PYTHONPATH=backend python scripts/seed.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the backend package importable regardless of invocation directory.
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.database import init_db  # noqa: E402


def main() -> None:
    init_db()
    print("Database initialized and challenges seeded.")


if __name__ == "__main__":
    main()
