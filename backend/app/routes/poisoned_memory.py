"""Poisoned Memory challenge-specific endpoints.

    GET  /api/challenges/poisoned-memory/state      records, last turn, ranking
    POST /api/challenges/poisoned-memory/ask        ask the Northstar Devices assistant
    POST /api/challenges/poisoned-memory/inspect    open one record's content and trust metadata
    POST /api/challenges/poisoned-memory/evidence   submit the poisoning marker
    POST /api/challenges/poisoned-memory/reset      clear this challenge's state

The client sends only a question, a record id or a marker. Ranking, the answer
and the verdict are recomputed server-side; the flag is returned only by
``evidence`` when the poisoned turn and record inspection are both confirmed,
and is never part of ``/state``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..challenges.poisoned_memory import SLUG, simulator
from ..challenges.poisoned_memory import state as pm_state
from ..challenges.poisoned_memory.corpus import RECORDS, get_record
from ..config import get_settings
from ..database import get_db
from ..models import PoisonedMemorySession
from ..rate_limit import build_limiter
from ..schemas import (
    PoisonedMemoryAskRequest,
    PoisonedMemoryEvidenceRequest,
    PoisonedMemoryEvidenceResponse,
    PoisonedMemoryInspectRequest,
    PoisonedMemoryInspectResponse,
    PoisonedMemoryPlayerRequest,
    PoisonedMemoryRecordDetail,
    PoisonedMemoryRecordSummary,
    PoisonedMemoryRetrieved,
    PoisonedMemoryState,
    SecurityAnalysis,
)
from ..services import flag_store, progress

router = APIRouter(prefix="/api/challenges/poisoned-memory", tags=["poisoned-memory"])
logger = logging.getLogger("ctf.poisoned_memory")
settings = get_settings()

_rate_limiter = build_limiter(settings.predict_rate_limit)

_ANALYSIS = SecurityAnalysis(
    owasp="LLM04:2025",
    root_cause=(
        "An unverified, tampered record entered the knowledge base and the "
        "ranker let its inflated score override the authoritative source"
    ),
    what_happened=[
        "A normal question retrieved both the manufacturer manual and a community record.",
        "The community record carried a false fact and an inflated ranking score. Provenance was not enforced when choosing evidence, so it ranked first.",
        "The assistant repeated the false component. No instruction was injected: the data itself was corrupted. That is the difference from prompt injection.",
        "This simulates poisoned retrieval data only. It does not demonstrate model-weight or training-time poisoning; real impact depends on the dataset, model and surrounding controls.",
        "A matching checksum would show a record is unchanged, not that it is true: integrity and provenance are related but distinct.",
    ],
    broken=(
        "score = overlap * 10 + record.rank_boost   # boost ignores trust/provenance\n"
        "answer = top_ranked(records).answer"
    ),
    secure=(
        "Validate provenance and integrity before ingestion; separate authoritative from community content\n"
        "Enforce source trust in application code so raw scores cannot override policy\n"
        "Review, version, audit and be able to roll back knowledge-base updates\n"
        "Test retrieval against known-good fixtures and monitor unexpected source dominance\n"
        "Cross-check with multiple independent trusted sources where appropriate"
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
    sess: PoisonedMemorySession | None, unlocked: bool
) -> PoisonedMemoryState:
    ranking = []
    if sess is not None:
        for item in pm_state.retrieved(sess):
            rec = get_record(str(item.get("record_id")))
            if rec is not None:
                ranking.append(
                    PoisonedMemoryRetrieved(
                        rank=int(item["rank"]),
                        record_id=rec.record_id,
                        source=rec.source,
                        trust=rec.trust,
                        relevance=int(item["relevance"]),
                        score=int(item["score"]),
                    )
                )
    return PoisonedMemoryState(
        status="solved" if unlocked else "active",
        max_query_length=simulator.MAX_QUERY_LENGTH,
        records=[
            PoisonedMemoryRecordSummary(
                record_id=r.record_id, source=r.source, trust=r.trust
            )
            for r in RECORDS
        ],
        query=sess.query if sess else "",
        response=sess.response if sess else None,
        retrieved=ranking,
        challenge_solved=unlocked,
        analysis=_ANALYSIS if unlocked else None,
    )


@router.get("/state", response_model=PoisonedMemoryState)
def get_state(
    player_id: str = "local-player", db: Session = Depends(get_db)
) -> PoisonedMemoryState:
    _check_player_id(player_id)
    row = _challenge_row(db)
    progress.ensure_player(db, player_id)
    sess = pm_state.ensure_session(db, player_id)
    db.commit()
    return _build_state(sess, progress.is_unlocked(db, player_id, row.id))


@router.post("/ask", response_model=PoisonedMemoryState)
def ask(
    request: Request, payload: PoisonedMemoryAskRequest, db: Session = Depends(get_db)
) -> PoisonedMemoryState:
    _rate_limit(request)
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    try:
        sess = pm_state.ask(db, payload.player_id, payload.query)
    except simulator.QueryInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    # Never log the question itself - it is untrusted text.
    logger.info(
        "poisoned-memory ask player=%s query_len=%d poisoned=%s",
        payload.player_id,
        len(sess.query),
        sess.poisoned,
    )
    return _build_state(sess, progress.is_unlocked(db, payload.player_id, row.id))


@router.post("/inspect", response_model=PoisonedMemoryInspectResponse)
def inspect(
    request: Request,
    payload: PoisonedMemoryInspectRequest,
    db: Session = Depends(get_db),
) -> PoisonedMemoryInspectResponse:
    _rate_limit(request)
    row = _challenge_row(db)
    rec = get_record(payload.record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Record not found")
    progress.ensure_player(db, payload.player_id)
    sess = pm_state.mark_inspected(db, payload.player_id, rec.record_id)
    db.commit()
    return PoisonedMemoryInspectResponse(
        record=PoisonedMemoryRecordDetail(
            record_id=rec.record_id,
            source=rec.source,
            trust=rec.trust,
            integrity=rec.integrity,
            content=rec.content,
            note=rec.note,
        ),
        state=_build_state(sess, progress.is_unlocked(db, payload.player_id, row.id)),
    )


@router.post("/evidence", response_model=PoisonedMemoryEvidenceResponse)
def evidence(
    request: Request,
    payload: PoisonedMemoryEvidenceRequest,
    db: Session = Depends(get_db),
) -> PoisonedMemoryEvidenceResponse:
    _rate_limit(request)
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    sess = pm_state.ensure_session(db, payload.player_id)
    verified = pm_state.verify_evidence(sess, payload.marker)
    flag: str | None = None
    if verified:
        progress.mark_unlocked(db, payload.player_id, row.id)
        flag = flag_store.load_flag(SLUG)
    db.commit()
    logger.info(
        "poisoned-memory evidence player=%s verified=%s", payload.player_id, verified
    )
    return PoisonedMemoryEvidenceResponse(
        solved_condition=verified,
        flag=flag,
        state=_build_state(sess, progress.is_unlocked(db, payload.player_id, row.id)),
    )


@router.post("/reset", response_model=PoisonedMemoryState)
def reset(
    payload: PoisonedMemoryPlayerRequest, db: Session = Depends(get_db)
) -> PoisonedMemoryState:
    """Clear this player's Poisoned Memory turn. Solves and other challenges are untouched."""
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    sess = pm_state.reset_player(db, payload.player_id)
    db.commit()
    logger.info("poisoned-memory reset player=%s", payload.player_id)
    return _build_state(sess, progress.is_unlocked(db, payload.player_id, row.id))
