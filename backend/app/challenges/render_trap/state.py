"""Per-player RenderTrap session state and proof validation.

All state is additive and scoped by ``player_id``. The nonce is a short-lived,
per-generation correlation token for the preview frame - it is NOT the flag and
not a reusable secret. Solving still goes through the platform's normal
unlock + flag flow; this module only decides whether a proof event is valid.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import RenderTrapSession
from . import simulator

NONCE_TTL = timedelta(minutes=10)

STATUS_NONE = "none"
STATUS_CONFIRMED = "confirmed"

# Reasons a proof is rejected. Deliberately coarse so responses do not help an
# attacker distinguish "wrong nonce" from "stale generation".
REJECT_NO_SESSION = "no_active_preview"
REJECT_INVALID = "invalid_proof"
REJECT_EXPIRED = "expired_proof"
REJECT_NOT_MARKUP = "no_markup"


def _now() -> datetime:
    # SQLite hands back naive datetimes; keep everything naive-UTC.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_session(session: Session, player_id: str) -> RenderTrapSession | None:
    return session.scalar(
        select(RenderTrapSession).where(RenderTrapSession.player_id == player_id)
    )


def ensure_session(session: Session, player_id: str) -> RenderTrapSession:
    row = get_session(session, player_id)
    if row is None:
        row = RenderTrapSession(
            player_id=player_id, generation=0, proof_status=STATUS_NONE
        )
        session.add(row)
        session.flush()
    return row


def submit_note(session: Session, player_id: str, note: str | None) -> RenderTrapSession:
    """Generate a fresh summary and rotate generation + nonce.

    Raises ``simulator.NoteTooLong`` for over-limit input.
    """
    cleaned = simulator.normalize_note(note)
    output = simulator.generate_summary(cleaned)
    row = ensure_session(session, player_id)
    row.note = cleaned
    row.raw_output = output
    row.generation += 1
    row.nonce = secrets.token_urlsafe(24)
    row.nonce_expires_at = _now() + NONCE_TTL
    row.proof_status = STATUS_NONE
    session.flush()
    return row


def reset_player(session: Session, player_id: str) -> RenderTrapSession:
    """Clear transient state and invalidate any outstanding frame.

    The generation counter keeps increasing so a delayed event from a
    pre-reset frame can never match again.
    """
    row = ensure_session(session, player_id)
    row.note = ""
    row.raw_output = None
    row.generation += 1
    row.nonce = None
    row.nonce_expires_at = None
    row.proof_status = STATUS_NONE
    session.flush()
    return row


def validate_proof(
    session: Session, player_id: str, *, generation: int, nonce: str
) -> tuple[bool, str | None]:
    """Check a proof event against the player's live session.

    On success the nonce is consumed (one-time) and ``(True, None)`` returned.
    The caller is responsible for the platform unlock.
    """
    row = get_session(session, player_id)
    if row is None or row.raw_output is None or row.nonce is None:
        return False, REJECT_NO_SESSION
    if row.proof_status == STATUS_CONFIRMED:
        return False, REJECT_INVALID
    if generation != row.generation or not secrets.compare_digest(
        nonce.encode("utf-8"), row.nonce.encode("utf-8")
    ):
        return False, REJECT_INVALID
    if row.nonce_expires_at is None or row.nonce_expires_at < _now():
        return False, REJECT_EXPIRED
    if not simulator.has_markup(row.raw_output):
        return False, REJECT_NOT_MARKUP
    row.proof_status = STATUS_CONFIRMED
    row.nonce = None
    row.nonce_expires_at = None
    session.flush()
    return True, None
