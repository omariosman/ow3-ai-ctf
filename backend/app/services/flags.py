"""Flag generation and verification (plan sections 15 & 20).

Flags follow the format OWASP{<tag>_<random_suffix>} (default tag: mirror). Only the SHA-256 hash is
persisted; the plaintext is generated once at seed time, handed to the backend
in-process, and never written to the database, metadata, or frontend.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

FLAG_PREFIX = "OWASP{mirror_"
FLAG_SUFFIX = "}"


def generate_flag(prefix: str = FLAG_PREFIX) -> str:
    """Create a fresh, random-looking flag for a challenge instance.

    ``prefix`` lets a challenge pick its own tag (e.g. ``OWASP{release_``); the
    default keeps Model Mirror's original ``OWASP{mirror_`` format.
    """
    suffix = secrets.token_hex(8)
    return f"{prefix}{suffix}{FLAG_SUFFIX}"


def hash_flag(flag: str) -> str:
    return hashlib.sha256(flag.strip().encode("utf-8")).hexdigest()


def verify_flag(submitted: str, expected_hash: str) -> bool:
    """Constant-time comparison of a submitted flag against the stored hash."""
    return hmac.compare_digest(hash_flag(submitted), expected_hash)
