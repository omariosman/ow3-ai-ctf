"""Per-player Poisoned Memory session state and server-side verification.

The client sends a question, a record id to inspect, or a marker string.
Ranking, the answer and every verdict are recomputed here.
"""

from __future__ import annotations

import hmac
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import PoisonedMemorySession
from . import simulator
from .corpus import (
    AUTHORITATIVE_ID,
    FALSE_COMPONENT,
    POISON_MARKER,
    POISONED_ID,
)


def get_session(session: Session, player_id: str) -> PoisonedMemorySession | None:
    return session.scalar(
        select(PoisonedMemorySession).where(PoisonedMemorySession.player_id == player_id)
    )


def ensure_session(session: Session, player_id: str) -> PoisonedMemorySession:
    row = get_session(session, player_id)
    if row is None:
        row = PoisonedMemorySession(player_id=player_id)
        session.add(row)
        session.flush()
    return row


def retrieved(row: PoisonedMemorySession) -> list[dict]:
    try:
        value = json.loads(row.retrieved or "[]")
    except ValueError:
        return []
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def verify_outcome(query: str, ranked: list[simulator.Ranked], response: str) -> bool:
    """The poisoned record was retrieved, ranked first above the authoritative
    one, and produced the false answer. Typing the marker as the query doesn't count."""
    ids = [r.record.record_id for r in ranked]
    return (
        POISON_MARKER not in query
        and bool(ids)
        and ids[0] == POISONED_ID
        and AUTHORITATIVE_ID in ids
        and FALSE_COMPONENT in response
    )


def ask(session: Session, player_id: str, query: str | None) -> PoisonedMemorySession:
    """Raises ``simulator.QueryInvalid`` for empty or over-limit input."""
    cleaned = simulator.normalize_query(query)
    ranked = simulator.rank(cleaned)
    response = simulator.answer(ranked)
    row = ensure_session(session, player_id)
    row.query = cleaned
    row.retrieved = json.dumps(
        [
            {
                "rank": i + 1,
                "record_id": r.record.record_id,
                "relevance": r.relevance,
                "score": r.score,
            }
            for i, r in enumerate(ranked)
        ]
    )
    row.response = response
    row.poisoned = verify_outcome(cleaned, ranked, response)
    session.flush()
    return row


def mark_inspected(session: Session, player_id: str, record_id: str) -> PoisonedMemorySession:
    row = ensure_session(session, player_id)
    if record_id == POISONED_ID:
        row.inspected = True
        session.flush()
    return row


def verify_evidence(row: PoisonedMemorySession, marker: str | None) -> bool:
    return bool(
        row.poisoned
        and row.inspected
        and marker is not None
        and hmac.compare_digest(marker.strip().encode(), POISON_MARKER.encode())
    )


def reset_player(session: Session, player_id: str) -> PoisonedMemorySession:
    row = ensure_session(session, player_id)
    row.query = ""
    row.retrieved = "[]"
    row.response = None
    row.poisoned = False
    row.inspected = False
    session.flush()
    return row
