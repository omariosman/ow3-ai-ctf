"""Trace Leak challenge-specific endpoints.

    GET  /api/challenges/trace-leak/state      FAQ turn and solve status
    POST /api/challenges/trace-leak/ask        ask Northstar Support AI an FAQ question
    POST /api/challenges/trace-leak/trace      open the request trace (the leak)
    POST /api/challenges/trace-leak/evidence   submit the canary found in the trace
    POST /api/challenges/trace-leak/reset      clear this challenge's state

The trace returns only this challenge's static fictional data. The flag is
returned only by ``evidence`` when the server confirms the trace was opened and
the canary matches; it is never part of ``/state``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..challenges.trace_leak import SLUG, simulator
from ..challenges.trace_leak import state as tl_state
from ..challenges.trace_leak.data import FAQS
from ..config import get_settings
from ..database import get_db
from ..models import TraceLeakSession
from ..rate_limit import build_limiter
from ..schemas import (
    SecurityAnalysis,
    TraceLeakAskRequest,
    TraceLeakEvidenceRequest,
    TraceLeakEvidenceResponse,
    TraceLeakPlayerRequest,
    TraceLeakState,
    TraceLeakTrace,
    TraceLeakTraceResponse,
)
from ..services import flag_store, progress

router = APIRouter(prefix="/api/challenges/trace-leak", tags=["trace-leak"])
logger = logging.getLogger("ctf.trace_leak")
settings = get_settings()

_rate_limiter = build_limiter(settings.predict_rate_limit)

_ANALYSIS = SecurityAnalysis(
    owasp="LLM07:2025",
    root_cause=(
        "A diagnostic trace serialised the internal system prompt into a "
        "user-visible response instead of returning allowlisted metadata"
    ),
    what_happened=[
        "A trace feature added for troubleshooting returned request metadata and the full internal prompt template.",
        "No prompt injection was needed: the application disclosed the prompt itself.",
        "The prompt held internal instructions and a review tag. Prompts like this can reveal business logic and hidden behaviour.",
        "Prompt leakage does not by itself grant access to data or tools; impact depends on what else the application exposes and how authorization is enforced.",
        "A prompt is not a place for credentials or access control, and hiding it alone does not fix all LLM application risks.",
    ],
    broken=(
        "trace = {'request_id': rid, 'faq': faq_id, 'internal_prompt': SYSTEM_PROMPT}\n"
        "return trace   # whole template reaches the user"
    ),
    secure=(
        "Return allowlisted diagnostic fields only; never serialise internal prompts\n"
        "Require authentication/authorization for trace and debug features\n"
        "Minimise and redact diagnostics; disable debug outside trusted development\n"
        "Keep secrets and authorization decisions out of prompts; enforce them in code\n"
        "Test that prompt fields are absent from user-facing responses and traces"
    ),
)


def _challenge_row(db: Session):
    row = progress.get_challenge_row(db, SLUG)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return row


def _check_player_id(player_id: str) -> None:
    if not player_id or len(player_id) > 80:
        raise HTTPException(status_code=422, detail="Invalid player id")


def _rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    if not _rate_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")


def _build_state(sess: TraceLeakSession | None, unlocked: bool) -> TraceLeakState:
    return TraceLeakState(
        status="solved" if unlocked else "active",
        max_question_length=simulator.MAX_QUESTION_LENGTH,
        sample_questions=[f.question for f in FAQS],
        question=sess.question if sess else "",
        response=sess.response if sess else None,
        challenge_solved=unlocked,
        analysis=_ANALYSIS if unlocked else None,
    )


@router.get("/state", response_model=TraceLeakState)
def get_state(
    player_id: str = "local-player", db: Session = Depends(get_db)
) -> TraceLeakState:
    _check_player_id(player_id)
    row = _challenge_row(db)
    progress.ensure_player(db, player_id)
    sess = tl_state.ensure_session(db, player_id)
    db.commit()
    return _build_state(sess, progress.is_unlocked(db, player_id, row.id))


@router.post("/ask", response_model=TraceLeakState)
def ask(
    request: Request, payload: TraceLeakAskRequest, db: Session = Depends(get_db)
) -> TraceLeakState:
    _rate_limit(request)
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    try:
        sess = tl_state.ask(db, payload.player_id, payload.question)
    except simulator.QuestionInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    # Never log the question itself - it is untrusted text.
    logger.info(
        "trace-leak ask player=%s question_len=%d", payload.player_id, len(sess.question)
    )
    return _build_state(sess, progress.is_unlocked(db, payload.player_id, row.id))


@router.post("/trace", response_model=TraceLeakTraceResponse)
def trace(
    request: Request, payload: TraceLeakPlayerRequest, db: Session = Depends(get_db)
) -> TraceLeakTraceResponse:
    """The intentionally vulnerable diagnostics action."""
    _rate_limit(request)
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    sess, data = tl_state.inspect_trace(db, payload.player_id)
    db.commit()
    logger.info("trace-leak trace player=%s", payload.player_id)
    return TraceLeakTraceResponse(
        trace=TraceLeakTrace(**data),
        state=_build_state(sess, progress.is_unlocked(db, payload.player_id, row.id)),
    )


@router.post("/evidence", response_model=TraceLeakEvidenceResponse)
def evidence(
    request: Request,
    payload: TraceLeakEvidenceRequest,
    db: Session = Depends(get_db),
) -> TraceLeakEvidenceResponse:
    _rate_limit(request)
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    sess = tl_state.ensure_session(db, payload.player_id)
    verified = tl_state.verify_evidence(sess, payload.canary)
    flag: str | None = None
    if verified:
        progress.mark_unlocked(db, payload.player_id, row.id)
        flag = flag_store.load_flag(SLUG)
    db.commit()
    logger.info(
        "trace-leak evidence player=%s verified=%s", payload.player_id, verified
    )
    return TraceLeakEvidenceResponse(
        solved_condition=verified,
        flag=flag,
        state=_build_state(sess, progress.is_unlocked(db, payload.player_id, row.id)),
    )


@router.post("/reset", response_model=TraceLeakState)
def reset(
    payload: TraceLeakPlayerRequest, db: Session = Depends(get_db)
) -> TraceLeakState:
    """Clear this player's Trace Leak turn. Solves and other challenges are untouched."""
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    sess = tl_state.reset_player(db, payload.player_id)
    db.commit()
    logger.info("trace-leak reset player=%s", payload.player_id)
    return _build_state(sess, progress.is_unlocked(db, payload.player_id, row.id))
