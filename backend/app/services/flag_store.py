"""Server-side plaintext flag store.

The database keeps only the SHA-256 hash (used to verify submissions). To *reveal*
the flag to a player who has met the deterministic solve condition, the backend
needs the plaintext. We keep it in a gitignored, server-only directory — never in
the database rows the challenge API returns, never in metadata, never in the
frontend, and never in a player-exposed environment variable (plan section 16).

Keeping it in a file (rather than only in memory) means the same flag survives a
backend restart and stays consistent with the hash already stored in the DB.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..config import get_settings

_FLAG_DIR = Path(get_settings().secrets_dir)


def _flag_path(slug: str) -> Path:
    safe = "".join(c for c in slug if c.isalnum() or c in "-_")
    return _FLAG_DIR / f"{safe}.flag"


def store_flag(slug: str, flag: str) -> None:
    _FLAG_DIR.mkdir(parents=True, exist_ok=True)
    path = _flag_path(slug)
    path.write_text(flag, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # best-effort on platforms without POSIX permissions


def load_flag(slug: str) -> str | None:
    path = _flag_path(slug)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def has_flag(slug: str) -> bool:
    return _flag_path(slug).exists()
