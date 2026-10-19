"""Context Hijack challenge-specific endpoints.

    GET  /api/challenges/context-hijack/state   documents, last turn, sources
    POST /api/challenges/context-hijack/ask     ask HelpDesk Atlas a question
    POST /api/challenges/context-hijack/reset   clear this challenge's state

The client sends only a question. Retrieval, the simulated response and the
solve verdict are all computed server-side; the flag is returned only by an
``ask`` whose recomputed outcome passes verification (same unlock + flag-store
flow as the other challenges) and is never part of ``/state``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..challenges.context_hijack import SLUG, simulator
from ..challenges.context_hijack import state as ch_state
from ..challenges.context_hijack.corpus import DOCUMENTS, get_document
from ..config import get_settings
from ..database import get_db
from ..models import ContextHijackSession
from ..rate_limit import build_limiter
from ..schemas import (
    ContextHijackAskRequest,
    ContextHijackAskResponse,
    ContextHijackDocument,
    ContextHijackPlayerRequest,
    ContextHijackSource,
    ContextHijackState,
    SecurityAnalysis,
)
from ..services import flag_store, progress

router = APIRouter(prefix="/api/challenges/context-hijack", tags=["context-hijack"])
logger = logging.getLogger("ctf.context_hijack")
settings = get_settings()

_rate_limiter = build_limiter(settings.predict_rate_limit)

_ANALYSIS = SecurityAnalysis(
    owasp="LLM01:2025",
    root_cause=(
        "Untrusted retrieved text was merged with trusted instructions without "
        "a reliable trust boundary (indirect prompt injection)"
    ),
    what_happened=[
        "A normal question retrieved both the official policy and an external community FAQ.",
        "The FAQ contained text written as an instruction. The context builder placed it next to the system instruction with nothing marking it as data.",
        "The assistant followed the embedded directive, so the answer was manipulated: it claimed lifetime refunds.",
        "Impact depends on what the assistant can reach. Here only the answer changed; with tools or private data in scope the same flaw can do more.",
        "RAG does not remove prompt injection, and no single mitigation fully solves it. Layer defences.",
    ],
    broken=(
        "context = SYSTEM_PROMPT + official_doc + community_faq   # one flat string\n"
        "answer = llm(context)   # instructions hidden in the FAQ are obeyed (pseudocode)"
    ),
    secure=(
        "Label and isolate retrieved content as untrusted data, never as instructions\n"
        "Prefer trusted sources for policy answers; enforce policy and authorization in\n"
        "ordinary application code, not in the prompt\n"
        "Give the assistant least privilege; require human approval for consequential actions\n"
        "Validate outputs against the trusted source; test adversarially (defence in depth)"
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
    sess: ContextHijackSession | None, unlocked: bool
) -> ContextHijackState:
    sources = []
    if sess is not None:
        for doc_id in ch_state.retrieved_ids(sess):
            doc = get_document(doc_id)
            if doc is not None:
                sources.append(
                    ContextHijackSource(
                        doc_id=doc.doc_id, title=doc.title, trusted=doc.trusted
                    )
                )
    return ContextHijackState(
        status="solved" if unlocked else "active",
        max_query_length=simulator.MAX_QUERY_LENGTH,
        documents=[
            ContextHijackDocument(
                doc_id=d.doc_id,
                title=d.title,
                source=d.source,
                trusted=d.trusted,
                content=d.body,
            )
            for d in DOCUMENTS
        ],
        query=sess.query if sess else "",
        response=sess.response if sess else None,
        sources=sources,
        challenge_solved=unlocked,
        analysis=_ANALYSIS if unlocked else None,
    )


@router.get("/state", response_model=ContextHijackState)
def get_state(
    player_id: str = "local-player", db: Session = Depends(get_db)
) -> ContextHijackState:
    _check_player_id(player_id)
    row = _challenge_row(db)
    progress.ensure_player(db, player_id)
    sess = ch_state.ensure_session(db, player_id)
    db.commit()
    return _build_state(sess, progress.is_unlocked(db, player_id, row.id))


@router.post("/ask", response_model=ContextHijackAskResponse)
def ask(
    request: Request,
    payload: ContextHijackAskRequest,
    db: Session = Depends(get_db),
) -> ContextHijackAskResponse:
    _rate_limit(request)
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    try:
        result = ch_state.ask(db, payload.player_id, payload.query)
    except simulator.QueryInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    flag: str | None = None
    if result.verified:
        progress.mark_unlocked(db, payload.player_id, row.id)
        flag = flag_store.load_flag(SLUG)
    db.commit()
    # Never log the question itself - it is untrusted text.
    logger.info(
        "context-hijack ask player=%s query_len=%d verified=%s",
        payload.player_id,
        len(result.session.query),
        result.verified,
    )
    return ContextHijackAskResponse(
        solved_condition=result.verified,
        flag=flag,
        state=_build_state(
            result.session, progress.is_unlocked(db, payload.player_id, row.id)
        ),
    )


@router.post("/reset", response_model=ContextHijackState)
def reset(
    payload: ContextHijackPlayerRequest, db: Session = Depends(get_db)
) -> ContextHijackState:
    """Clear this player's Context Hijack turn. Solves and other challenges are untouched."""
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    sess = ch_state.reset_player(db, payload.player_id)
    db.commit()
    logger.info("context-hijack reset player=%s", payload.player_id)
    return _build_state(sess, progress.is_unlocked(db, payload.player_id, row.id))
