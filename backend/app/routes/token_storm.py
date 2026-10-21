"""Token Storm challenge-specific endpoints.

    GET  /api/challenges/token-storm/state    ledger, policy, history, checks
    POST /api/challenges/token-storm/request  send one simulated gateway request
    POST /api/challenges/token-storm/policy   replace the gateway policy
    POST /api/challenges/token-storm/verify   run the hardening checks
    POST /api/challenges/token-storm/reset    clear this challenge's state

Everything is simulated. The client sends only token counts and policy limits;
costs, the budget, the abuse evidence and the verdict are computed server-side.
The flag is returned only by ``verify`` after the server has recorded an abuse
reproduction and all four checks pass against the current policy, and is never
part of ``/state``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..challenges.token_storm import SLUG, simulator
from ..challenges.token_storm import state as ts_state
from ..config import get_settings
from ..database import get_db
from ..models import TokenStormSession
from ..rate_limit import build_limiter
from ..schemas import (
    SecurityAnalysis,
    TokenStormCheck,
    TokenStormHistoryItem,
    TokenStormPlayerRequest,
    TokenStormPolicy,
    TokenStormPolicyRequest,
    TokenStormRequest,
    TokenStormRequestResponse,
    TokenStormState,
    TokenStormVerifyResponse,
)
from ..services import flag_store, progress

router = APIRouter(prefix="/api/challenges/token-storm", tags=["token-storm"])
logger = logging.getLogger("ctf.token_storm")
settings = get_settings()

_rate_limiter = build_limiter(settings.predict_rate_limit)

_COST_FORMULA = (
    "simulated_cost = 2 + ceil(input_tokens / 100) + ceil(output_tokens / 50)  "
    "(all token counts and costs are simulated; starting budget 100 units)"
)

_ANALYSIS = SecurityAnalysis(
    owasp="LLM10:2025",
    root_cause=(
        "The gateway enforced no input, output, quota or budget limits, so a "
        "single oversized or a few repeated requests could drain the budget"
    ),
    what_happened=[
        "With enforcement off, one large-input or large-output request cost over half the simulated budget, and a second exhausted it.",
        "You enabled layered limits in the authoritative gateway: input size, output cap, request quota and a budget ceiling.",
        "The server then re-ran abusive and normal requests against your policy: abuse was blocked for the right reasons and a normal request still succeeded.",
        "Prompt instructions are not a substitute for application-level enforcement; controls belong at the server/gateway boundary.",
        "Real systems also need timeouts, rate limiting, monitoring and safe rejection behaviour. This lab is a simplified simulator, not a production rate limiter.",
    ],
    broken=(
        "cost = overhead + input + output\n"
        "serve(request)   # no caps, no quota, no ceiling: budget = budget - cost"
    ),
    secure=(
        "Cap input size and requested output tokens per request\n"
        "Apply per-user quotas / rate limits and a budget ceiling before serving\n"
        "Reject early with clear messages; never let a rejected request consume budget\n"
        "Add timeouts and usage monitoring/alerting\n"
        "Test that abuse is blocked and that legitimate requests still succeed"
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


def _build_state(sess: TokenStormSession, unlocked: bool) -> TokenStormState:
    ledger = ts_state.ledger_of(sess)
    policy = ts_state.policy_of(sess)
    return TokenStormState(
        status="solved" if unlocked else "active",
        initial_budget=simulator.INITIAL_BUDGET,
        remaining_budget=ledger.remaining_budget,
        request_count=ledger.request_count,
        policy=TokenStormPolicy(**policy.__dict__),
        history=[TokenStormHistoryItem(**h) for h in ledger.history],
        abuse_demonstrated=sess.abuse_demonstrated,
        checks=[TokenStormCheck(**c) for c in ts_state.checks_of(sess)],
        hardening_verified=sess.verified,
        cost_formula=_COST_FORMULA,
        challenge_solved=unlocked,
        analysis=_ANALYSIS if unlocked else None,
    )


@router.get("/state", response_model=TokenStormState)
def get_state(
    player_id: str = "local-player", db: Session = Depends(get_db)
) -> TokenStormState:
    _check_player_id(player_id)
    row = _challenge_row(db)
    progress.ensure_player(db, player_id)
    sess = ts_state.ensure_session(db, player_id)
    db.commit()
    return _build_state(sess, progress.is_unlocked(db, player_id, row.id))


@router.post("/request", response_model=TokenStormRequestResponse)
def send_request(
    request: Request, payload: TokenStormRequest, db: Session = Depends(get_db)
) -> TokenStormRequestResponse:
    _rate_limit(request)
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    sess, result = ts_state.submit_request(
        db, payload.player_id, payload.input_tokens, payload.output_tokens
    )
    db.commit()
    logger.info(
        "token-storm request player=%s accepted=%s", payload.player_id, result.accepted
    )
    state = _build_state(sess, progress.is_unlocked(db, payload.player_id, row.id))
    return TokenStormRequestResponse(
        result=TokenStormHistoryItem(
            n=sess.request_count if result.accepted else None,
            input_tokens=payload.input_tokens,
            output_tokens=payload.output_tokens,
            **result.as_dict(),
        ),
        state=state,
    )


@router.post("/policy", response_model=TokenStormState)
def set_policy(
    request: Request, payload: TokenStormPolicyRequest, db: Session = Depends(get_db)
) -> TokenStormState:
    _rate_limit(request)
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    policy = simulator.Policy(
        max_input_tokens=payload.max_input_tokens,
        max_output_tokens=payload.max_output_tokens,
        max_requests=payload.max_requests,
        max_total_cost=payload.max_total_cost,
        enforcement_enabled=payload.enforcement_enabled,
    )
    try:
        sess = ts_state.set_policy(db, payload.player_id, policy)
    except simulator.PolicyInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    logger.info("token-storm policy player=%s", payload.player_id)
    return _build_state(sess, progress.is_unlocked(db, payload.player_id, row.id))


@router.post("/verify", response_model=TokenStormVerifyResponse)
def verify(
    request: Request, payload: TokenStormPlayerRequest, db: Session = Depends(get_db)
) -> TokenStormVerifyResponse:
    _rate_limit(request)
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    sess = ts_state.verify(db, payload.player_id)
    flag: str | None = None
    if sess.verified:
        progress.mark_unlocked(db, payload.player_id, row.id)
        flag = flag_store.load_flag(SLUG)
    db.commit()
    logger.info(
        "token-storm verify player=%s verified=%s", payload.player_id, sess.verified
    )
    return TokenStormVerifyResponse(
        solved_condition=sess.verified,
        flag=flag,
        state=_build_state(sess, progress.is_unlocked(db, payload.player_id, row.id)),
    )


@router.post("/reset", response_model=TokenStormState)
def reset(
    payload: TokenStormPlayerRequest, db: Session = Depends(get_db)
) -> TokenStormState:
    """Clear this player's Token Storm state. Solves and other challenges are untouched."""
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    sess = ts_state.reset_player(db, payload.player_id)
    db.commit()
    logger.info("token-storm reset player=%s", payload.player_id)
    return _build_state(sess, progress.is_unlocked(db, payload.player_id, row.id))
