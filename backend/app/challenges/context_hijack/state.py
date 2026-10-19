"""Per-player Context Hijack session state and server-side solve verification.

All state is additive and scoped by ``player_id``. The client supplies only a
question; retrieval, the response and the verdict are recomputed here. Solving
still goes through the platform's normal unlock + flag flow.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import ContextHijackSession
from . import simulator
from .corpus import INJECTION_MARKER, POISONED_ID


@dataclass(frozen=True)
class AskResult:
    session: ContextHijackSession
    verified: bool


def get_session(session: Session, player_id: str) -> ContextHijackSession | None:
    return session.scalar(
        select(ContextHijackSession).where(ContextHijackSession.player_id == player_id)
    )


def ensure_session(session: Session, player_id: str) -> ContextHijackSession:
    row = get_session(session, player_id)
    if row is None:
        row = ContextHijackSession(player_id=player_id)
        session.add(row)
        session.flush()
    return row


def retrieved_ids(row: ContextHijackSession) -> list[str]:
    try:
        value = json.loads(row.retrieved or "[]")
    except ValueError:
        return []
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def verify_outcome(query: str, retrieved: list[str], response: str) -> bool:
    """Evidence check: a real question retrieved the untrusted FAQ and the
    simulated assistant produced the injected outcome. Typing the marker as the
    question does not count."""
    return (
        INJECTION_MARKER not in query
        and POISONED_ID in retrieved
        and INJECTION_MARKER in response
        and "lifetime refund" in response
    )


def ask(session: Session, player_id: str, query: str | None) -> AskResult:
    """Raises ``simulator.QueryInvalid`` for empty or over-limit input."""
    cleaned = simulator.normalize_query(query)
    docs = simulator.retrieve(cleaned)
    response = simulator.answer(cleaned, docs)
    ids = [d.doc_id for d in docs]
    row = ensure_session(session, player_id)
    row.query = cleaned
    row.retrieved = json.dumps(ids)
    row.response = response
    row.injected = verify_outcome(cleaned, ids, response)
    session.flush()
    return AskResult(session=row, verified=row.injected)


def reset_player(session: Session, player_id: str) -> ContextHijackSession:
    row = ensure_session(session, player_id)
    row.query = ""
    row.retrieved = "[]"
    row.response = None
    row.injected = False
    session.flush()
    return row
