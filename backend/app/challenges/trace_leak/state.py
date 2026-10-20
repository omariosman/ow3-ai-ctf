"""Per-player Trace Leak session state and server-side evidence check.

The client sends only a question or a canary string. Matching, the trace and
the verdict are computed here; typing the canary without having opened the
trace solves nothing.
"""

from __future__ import annotations

import hmac

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import TraceLeakSession
from . import simulator
from .data import CANARY, FAQS


def get_session(session: Session, player_id: str) -> TraceLeakSession | None:
    return session.scalar(
        select(TraceLeakSession).where(TraceLeakSession.player_id == player_id)
    )


def ensure_session(session: Session, player_id: str) -> TraceLeakSession:
    row = get_session(session, player_id)
    if row is None:
        row = TraceLeakSession(player_id=player_id)
        session.add(row)
        session.flush()
    return row


def ask(session: Session, player_id: str, question: str | None) -> TraceLeakSession:
    """Raises ``simulator.QuestionInvalid`` for empty or over-limit input."""
    cleaned = simulator.normalize_question(question)
    faq = simulator.match_faq(cleaned)
    row = ensure_session(session, player_id)
    row.question = cleaned
    row.faq_id = faq.faq_id if faq else None
    row.response = simulator.answer(faq)
    session.flush()
    return row


def inspect_trace(session: Session, player_id: str) -> tuple[TraceLeakSession, dict]:
    """Return the (vulnerable) trace for the last turn and record that it was opened."""
    row = ensure_session(session, player_id)
    question = row.question or FAQS[0].question
    trace = simulator.build_trace(question, row.faq_id if row.question else FAQS[0].faq_id)
    row.trace_viewed = True
    session.flush()
    return row, trace


def verify_evidence(row: TraceLeakSession, canary: str | None) -> bool:
    return bool(
        row.trace_viewed
        and canary is not None
        and hmac.compare_digest(canary.strip().encode(), CANARY.encode())
    )


def reset_player(session: Session, player_id: str) -> TraceLeakSession:
    row = ensure_session(session, player_id)
    row.question = ""
    row.faq_id = None
    row.response = None
    row.trace_viewed = False
    session.flush()
    return row
