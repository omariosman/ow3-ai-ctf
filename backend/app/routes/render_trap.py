"""RenderTrap challenge-specific endpoints.

    GET  /api/challenges/render-trap/state    ticket, current output, preview doc
    POST /api/challenges/render-trap/summarize add a note, generate the summary
    POST /api/challenges/render-trap/proof    validate the preview's proof event
    POST /api/challenges/render-trap/reset    clear transient state

The backend treats the assistant output as an opaque string: it is stored and
returned, never parsed, rendered, or executed here. The flag is revealed only
in the /proof response of a valid, fresh, session-bound event, through the same
unlock + flag-store flow the other challenges use. It is never part of /state.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..challenges.render_trap import SLUG, simulator
from ..challenges.render_trap import state as rt_state
from ..challenges.render_trap.preview import build_preview_document
from ..config import get_settings
from ..database import get_db
from ..models import RenderTrapSession
from ..rate_limit import build_limiter
from ..schemas import (
    RenderTrapPlayerRequest,
    RenderTrapProofRequest,
    RenderTrapProofResponse,
    RenderTrapState,
    RenderTrapSubmitRequest,
    RenderTrapTicket,
    SecurityAnalysis,
)
from ..services import flag_store, progress

router = APIRouter(prefix="/api/challenges/render-trap", tags=["render-trap"])
logger = logging.getLogger("ctf.render_trap")
settings = get_settings()

_rate_limiter = build_limiter(settings.predict_rate_limit)

_ANALYSIS = SecurityAnalysis(
    owasp="LLM05:2025",
    root_cause="Improper Output Handling (model output rendered as trusted HTML)",
    what_happened=[
        "The assistant's output contained text that came from a user-influenced note.",
        "The dashboard preview inserted that output into an HTML document as markup.",
        "The browser therefore interpreted it, and script ran in the preview.",
        "Model output is untrusted data. Handle it for the context that consumes it.",
    ],
    broken="LLM output -> HTML preview (interpreted as markup) -> browser executes it",
    secure=(
        "LLM output -> render as text (React: {output})\n"
        "If rich text is required: maintained Markdown parser -> strict allowlist "
        "sanitizer -> render; CSP only as defense in depth"
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


def _build_state(
    row_session: RenderTrapSession | None,
    unlocked: bool,
) -> RenderTrapState:
    preview_html = None
    if row_session and row_session.raw_output is not None and row_session.nonce:
        preview_html = build_preview_document(
            row_session.raw_output,
            generation=row_session.generation,
            nonce=row_session.nonce,
        )
    return RenderTrapState(
        status="solved" if unlocked else "active",
        ticket=RenderTrapTicket(**simulator.TICKET),
        max_note_length=simulator.MAX_NOTE_LENGTH,
        note=row_session.note if row_session else "",
        raw_output=row_session.raw_output if row_session else None,
        generation=row_session.generation if row_session else 0,
        preview_html=preview_html,
        challenge_solved=unlocked,
        analysis=_ANALYSIS if unlocked else None,
    )


@router.get("/state", response_model=RenderTrapState)
def get_state(
    player_id: str = "local-player", db: Session = Depends(get_db)
) -> RenderTrapState:
    _check_player_id(player_id)
    row = _challenge_row(db)
    progress.ensure_player(db, player_id)
    sess = rt_state.ensure_session(db, player_id)
    db.commit()
    return _build_state(sess, progress.is_unlocked(db, player_id, row.id))


@router.post("/summarize", response_model=RenderTrapState)
def summarize(
    request: Request,
    payload: RenderTrapSubmitRequest,
    db: Session = Depends(get_db),
) -> RenderTrapState:
    _rate_limit(request)
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    try:
        sess = rt_state.submit_note(db, payload.player_id, payload.note)
    except simulator.NoteTooLong as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    # Never log the note itself - it is untrusted text.
    logger.info(
        "render-trap summarize player=%s generation=%s note_len=%d",
        payload.player_id,
        sess.generation,
        len(sess.note),
    )
    return _build_state(sess, progress.is_unlocked(db, payload.player_id, row.id))


@router.post("/proof", response_model=RenderTrapProofResponse)
def proof(
    request: Request,
    payload: RenderTrapProofRequest,
    db: Session = Depends(get_db),
) -> RenderTrapProofResponse:
    _rate_limit(request)
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)

    ok, reason = rt_state.validate_proof(
        db, payload.player_id, generation=payload.generation, nonce=payload.nonce
    )
    flag: str | None = None
    if ok:
        progress.mark_unlocked(db, payload.player_id, row.id)
        flag = flag_store.load_flag(SLUG)
    db.commit()

    logger.info(
        "render-trap proof player=%s accepted=%s reason=%s", payload.player_id, ok, reason
    )
    sess = rt_state.get_session(db, payload.player_id)
    return RenderTrapProofResponse(
        accepted=ok,
        reason=reason,
        flag=flag,
        state=_build_state(sess, progress.is_unlocked(db, payload.player_id, row.id)),
    )


@router.post("/reset", response_model=RenderTrapState)
def reset(
    payload: RenderTrapPlayerRequest, db: Session = Depends(get_db)
) -> RenderTrapState:
    """Clear this player's RenderTrap state. Solves and other challenges are untouched."""
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    sess = rt_state.reset_player(db, payload.player_id)
    db.commit()
    logger.info("render-trap reset player=%s", payload.player_id)
    return _build_state(sess, progress.is_unlocked(db, payload.player_id, row.id))
