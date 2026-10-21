"""Tenant Zero challenge-specific endpoints.

    GET  /api/challenges/tenant-zero/state     tenant, own conversations, policy, checks
    POST /api/challenges/tenant-zero/open      open a conversation by id
    POST /api/challenges/tenant-zero/summary   summarize a conversation by id
    POST /api/challenges/tenant-zero/search    search past conversations
    POST /api/challenges/tenant-zero/policy    replace the access policy
    POST /api/challenges/tenant-zero/verify    run the hardening checks
    POST /api/challenges/tenant-zero/reset     clear this challenge's state

The acting tenant is fixed server-side; the client never sends a tenant, role or
verdict. The flag is returned only by ``verify`` after the server recorded a
real cross-tenant leak and all four checks pass against the current policy, and
is never part of ``/state``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..challenges.tenant_zero import SLUG, simulator
from ..challenges.tenant_zero import state as tz_state
from ..challenges.tenant_zero.data import ACTING_TENANT, CONVERSATIONS, TENANT_NAMES
from ..config import get_settings
from ..database import get_db
from ..models import TenantZeroSession
from ..rate_limit import build_limiter
from ..schemas import (
    SecurityAnalysis,
    TenantZeroCheck,
    TenantZeroConversationRequest,
    TenantZeroConversationSummary,
    TenantZeroOpenResponse,
    TenantZeroPlayerRequest,
    TenantZeroPolicy,
    TenantZeroPolicyRequest,
    TenantZeroSearchRequest,
    TenantZeroSearchResponse,
    TenantZeroState,
    TenantZeroVerifyResponse,
)
from ..services import flag_store, progress

router = APIRouter(prefix="/api/challenges/tenant-zero", tags=["tenant-zero"])
logger = logging.getLogger("ctf.tenant_zero")
settings = get_settings()

_rate_limiter = build_limiter(settings.predict_rate_limit)

_ANALYSIS = SecurityAnalysis(
    owasp="LLM02:2025",
    root_cause=(
        "Conversation reads and retrieval never checked tenant ownership, and "
        "summaries copied sensitive fields without redaction"
    ),
    what_happened=[
        "Opening a conversation by id, searching, and summarizing all returned Tenant Beta's data to Tenant Alpha. Ownership existed as metadata that no code checked.",
        "You enabled server-side ownership checks, tenant-scoped search and redaction behind a master switch that is actually applied.",
        "The server then re-ran cross-tenant and legitimate requests against your policy: foreign data was denied, search was scoped, fields were masked, and your own conversations still worked.",
        "Telling an assistant not to share data is not access control; unguessable ids alone are not authorization either.",
        "Impact in real systems depends on what data is reachable and how authorization is enforced. Redaction alone does not fix a missing ownership check.",
    ],
    broken=(
        "conv = db.get(conversation_id)   # no check that conv.tenant == caller.tenant\n"
        "results = search(all_tenants, query)\n"
        "return summary(conv)             # raw email and account included"
    ),
    secure=(
        "Authorize every read with the server-held identity: deny by default, uniform denial message\n"
        "Scope retrieval to the caller's tenant before ranking or generation\n"
        "Minimise and redact sensitive fields; never put other tenants' data in a model's context\n"
        "Log and alert on cross-tenant attempts\n"
        "Regression-test with a second tenant: tenant A must never read tenant B"
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


def _build_state(sess: TenantZeroSession, unlocked: bool) -> TenantZeroState:
    return TenantZeroState(
        status="solved" if unlocked else "active",
        tenant_name=TENANT_NAMES[ACTING_TENANT],
        own_conversations=[
            TenantZeroConversationSummary(conv_id=c.conv_id, subject=c.subject)
            for c in CONVERSATIONS
            if c.tenant == ACTING_TENANT
        ],
        policy=TenantZeroPolicy(**tz_state.policy_of(sess).__dict__),
        leak_demonstrated=sess.leak_demonstrated,
        checks=[TenantZeroCheck(**c) for c in tz_state.checks_of(sess)],
        hardening_verified=sess.verified,
        max_query_length=simulator.MAX_QUERY_LENGTH,
        challenge_solved=unlocked,
        analysis=_ANALYSIS if unlocked else None,
    )


@router.get("/state", response_model=TenantZeroState)
def get_state(
    player_id: str = "local-player", db: Session = Depends(get_db)
) -> TenantZeroState:
    _check_player_id(player_id)
    row = _challenge_row(db)
    progress.ensure_player(db, player_id)
    sess = tz_state.ensure_session(db, player_id)
    db.commit()
    return _build_state(sess, progress.is_unlocked(db, player_id, row.id))


def _open_like(request, payload, db, action, label) -> TenantZeroOpenResponse:
    _rate_limit(request)
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    sess, result = action(db, payload.player_id, payload.conversation_id)
    db.commit()
    logger.info(
        "tenant-zero %s player=%s allowed=%s", label, payload.player_id, result.allowed
    )
    return TenantZeroOpenResponse(
        allowed=result.allowed,
        message=result.message,
        conversation=result.conversation,
        state=_build_state(sess, progress.is_unlocked(db, payload.player_id, row.id)),
    )


@router.post("/open", response_model=TenantZeroOpenResponse)
def open_conversation(
    request: Request, payload: TenantZeroConversationRequest, db: Session = Depends(get_db)
) -> TenantZeroOpenResponse:
    return _open_like(request, payload, db, tz_state.open_conversation, "open")


@router.post("/summary", response_model=TenantZeroOpenResponse)
def summary(
    request: Request, payload: TenantZeroConversationRequest, db: Session = Depends(get_db)
) -> TenantZeroOpenResponse:
    return _open_like(request, payload, db, tz_state.summarize, "summary")


@router.post("/search", response_model=TenantZeroSearchResponse)
def search(
    request: Request, payload: TenantZeroSearchRequest, db: Session = Depends(get_db)
) -> TenantZeroSearchResponse:
    _rate_limit(request)
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    try:
        sess, results = tz_state.search(db, payload.player_id, payload.query)
    except simulator.QueryInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    # Never log the query itself - it is untrusted text.
    logger.info("tenant-zero search player=%s results=%d", payload.player_id, len(results))
    return TenantZeroSearchResponse(
        results=results,
        state=_build_state(sess, progress.is_unlocked(db, payload.player_id, row.id)),
    )


@router.post("/policy", response_model=TenantZeroState)
def set_policy(
    request: Request, payload: TenantZeroPolicyRequest, db: Session = Depends(get_db)
) -> TenantZeroState:
    _rate_limit(request)
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    policy = simulator.Policy(
        enforce_ownership=payload.enforce_ownership,
        scope_search_to_tenant=payload.scope_search_to_tenant,
        redact_sensitive_fields=payload.redact_sensitive_fields,
        enforcement_enabled=payload.enforcement_enabled,
    )
    try:
        sess = tz_state.set_policy(db, payload.player_id, policy)
    except simulator.PolicyInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    logger.info("tenant-zero policy player=%s", payload.player_id)
    return _build_state(sess, progress.is_unlocked(db, payload.player_id, row.id))


@router.post("/verify", response_model=TenantZeroVerifyResponse)
def verify(
    request: Request, payload: TenantZeroPlayerRequest, db: Session = Depends(get_db)
) -> TenantZeroVerifyResponse:
    _rate_limit(request)
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    sess = tz_state.verify(db, payload.player_id)
    flag: str | None = None
    if sess.verified:
        progress.mark_unlocked(db, payload.player_id, row.id)
        flag = flag_store.load_flag(SLUG)
    db.commit()
    logger.info("tenant-zero verify player=%s verified=%s", payload.player_id, sess.verified)
    return TenantZeroVerifyResponse(
        solved_condition=sess.verified,
        flag=flag,
        state=_build_state(sess, progress.is_unlocked(db, payload.player_id, row.id)),
    )


@router.post("/reset", response_model=TenantZeroState)
def reset(
    payload: TenantZeroPlayerRequest, db: Session = Depends(get_db)
) -> TenantZeroState:
    """Clear this player's Tenant Zero state. Solves and other challenges are untouched."""
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    sess = tz_state.reset_player(db, payload.player_id)
    db.commit()
    logger.info("tenant-zero reset player=%s", payload.player_id)
    return _build_state(sess, progress.is_unlocked(db, payload.player_id, row.id))
