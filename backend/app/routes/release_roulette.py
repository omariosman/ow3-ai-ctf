"""Release Roulette challenge-specific endpoints.

    POST /api/challenges/release-roulette/chat    talk to ReleaseBot
    GET  /api/challenges/release-roulette/state   public release + audit state
    POST /api/challenges/release-roulette/reset   restore Project Aurora

After every chat turn the deterministic validator inspects the simulated
deployment state. When aurora-4.8.1 has been rolled back by ReleaseBot, the
player's progress is marked unlocked and the flag is returned (same flow as
Model Mirror). The flag is never part of /state.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..challenges.release_roulette import SLUG
from ..challenges.release_roulette import deployment_state as rr_state
from ..challenges.release_roulette import validator as rr_validator
from ..challenges.release_roulette.agent import ACTOR, ReleaseRouletteAgent
from ..challenges.release_roulette.tools import ToolContext
from ..config import get_settings
from ..database import get_db
from ..rate_limit import build_limiter
from ..schemas import (
    AuditEvent,
    ReleaseRouletteChatRequest,
    ReleaseRouletteChatResponse,
    ReleaseRoulettePlayerRequest,
    ReleaseRouletteState,
    ReleaseView,
    SecurityAnalysis,
    ToolCall,
)
from ..services import flag_store, progress

router = APIRouter(prefix="/api/challenges/release-roulette", tags=["release-roulette"])
logger = logging.getLogger("ctf.release_roulette")
settings = get_settings()

# Same basic IP-keyed limiter the platform already uses for Model Mirror.
_rate_limiter = build_limiter(settings.predict_rate_limit)
_agent = ReleaseRouletteAgent()

_ANALYSIS = SecurityAnalysis(
    owasp="LLM06:2025",
    root_cause="Excessive Agency (excessive functionality + excessive autonomy)",
    what_happened=[
        "ReleaseBot had access to a deployment operation that was not necessary for its job.",
        "The application trusted the agent to decide when that operation should be used.",
        "That is an authorization failure at the architecture level.",
        "The correct fix is not a stronger system prompt. Remove unnecessary capabilities, "
        "enforce authorization outside the model, and require approval for high-impact operations.",
    ],
    broken="AI Agent -> Broad Deployment Tool -> Production State",
    secure=(
        "AI Agent -> Least-Privilege Tools (inspect, report, stage)\n"
        "AI proposes rollback -> Authorization Layer -> Human Approval -> Privileged Action"
    ),
)


def _challenge_row(db: Session):
    row = progress.get_challenge_row(db, SLUG)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return row


def _build_state(db: Session, player_id: str, challenge_id: int) -> ReleaseRouletteState:
    releases = rr_state.list_releases(db, player_id)
    unlocked = progress.is_unlocked(db, player_id, challenge_id)
    return ReleaseRouletteState(
        status="solved" if unlocked else "active",
        target_release=rr_validator.TARGET_RELEASE,
        releases=[ReleaseView(**vars(rr_state.ReleaseView.from_row(r))) for r in releases],
        audit=[
            AuditEvent(
                request_id=a.request_id,
                tool=a.tool,
                release_id=a.release_id,
                actor=a.actor,
                ok=a.ok,
                transition=a.transition,
                timestamp=a.created_at.isoformat(timespec="seconds"),
            )
            for a in rr_state.recent_audit(db, player_id)
        ],
        challenge_solved=unlocked,
        analysis=_ANALYSIS if unlocked else None,
    )


@router.post("/chat", response_model=ReleaseRouletteChatResponse)
def chat(
    request: Request,
    payload: ReleaseRouletteChatRequest,
    db: Session = Depends(get_db),
) -> ReleaseRouletteChatResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not _rate_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")

    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    rr_state.ensure_releases(db, payload.player_id)

    request_id = uuid.uuid4().hex[:12]
    ctx = ToolContext(
        session=db, player_id=payload.player_id, actor=ACTOR, request_id=request_id
    )
    turn = _agent.run(ctx, payload.message)

    target = rr_state.get_release(db, payload.player_id, rr_validator.TARGET_RELEASE)
    solved_condition = rr_validator.is_solved(target)

    flag: str | None = None
    note: str | None = None
    if solved_condition:
        progress.mark_unlocked(db, payload.player_id, row.id)
        flag = flag_store.load_flag(SLUG)
        note = "Solve condition met: the protected release was rolled back by ReleaseBot."
    db.commit()

    logger.info(
        "release-roulette chat request=%s player=%s challenge=%s tools=%s solved=%s",
        request_id,
        payload.player_id,
        SLUG,
        ",".join(e.tool for e in turn.tool_calls) or "-",
        solved_condition,
    )

    return ReleaseRouletteChatResponse(
        request_id=request_id,
        reply=turn.reply,
        tool_calls=[ToolCall(**vars(e)) for e in turn.tool_calls],
        state=_build_state(db, payload.player_id, row.id),
        solved_condition=solved_condition,
        flag=flag,
        note=note,
    )


@router.get("/state", response_model=ReleaseRouletteState)
def get_state(
    player_id: str = "local-player", db: Session = Depends(get_db)
) -> ReleaseRouletteState:
    if len(player_id) > 80:
        raise HTTPException(status_code=422, detail="Invalid player id")
    row = _challenge_row(db)
    progress.ensure_player(db, player_id)
    rr_state.ensure_releases(db, player_id)
    db.commit()
    return _build_state(db, player_id, row.id)


@router.post("/reset", response_model=ReleaseRouletteState)
def reset(
    payload: ReleaseRoulettePlayerRequest, db: Session = Depends(get_db)
) -> ReleaseRouletteState:
    """Restore this player's Project Aurora. Solves and other challenges are untouched."""
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    rr_state.reset_player(db, payload.player_id)
    db.commit()
    logger.info("release-roulette reset player=%s", payload.player_id)
    return _build_state(db, payload.player_id, row.id)
