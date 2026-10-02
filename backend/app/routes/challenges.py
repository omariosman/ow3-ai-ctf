"""Generic challenge endpoints (plan section 10)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import Submission
from ..schemas import (
    ChallengeDetail,
    ChallengeSummary,
    Hint,
    SubmitRequest,
    SubmitResponse,
)
from ..services import flags, progress
from ..services.registry import all_challenges, get_challenge

router = APIRouter(prefix="/api/challenges", tags=["challenges"])
logger = logging.getLogger("ctf.challenges")
settings = get_settings()


@router.get("", response_model=list[ChallengeSummary])
def list_challenges(
    player_id: str = "local-player", db: Session = Depends(get_db)
) -> list[ChallengeSummary]:
    out: list[ChallengeSummary] = []
    for challenge in all_challenges():
        meta = challenge.get_public_metadata()
        row = progress.get_challenge_row(db, meta.slug)
        if row is None or not row.is_active:
            continue
        solved = progress.is_solved(db, player_id, row.id)
        out.append(
            ChallengeSummary(
                slug=meta.slug,
                title=meta.title,
                category=meta.category,
                difficulty=meta.difficulty,
                points=meta.points,
                author=meta.author,
                solved=solved,
            )
        )
    return out


@router.get("/{slug}", response_model=ChallengeDetail)
def get_challenge_detail(
    slug: str, player_id: str = "local-player", db: Session = Depends(get_db)
) -> ChallengeDetail:
    challenge = get_challenge(slug)
    row = progress.get_challenge_row(db, slug)
    if challenge is None or row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Challenge not found")

    meta = challenge.get_public_metadata()
    return ChallengeDetail(
        slug=meta.slug,
        title=meta.title,
        category=meta.category,
        difficulty=meta.difficulty,
        points=meta.points,
        author=meta.author,
        description=meta.description,
        learning_objectives=meta.learning_objectives,
        hints=[Hint(order=h.order, cost=h.cost, text=h.text) for h in meta.hints],
        solved=progress.is_solved(db, player_id, row.id),
        unlocked=progress.is_unlocked(db, player_id, row.id),
    )


@router.post("/{slug}/submit", response_model=SubmitResponse)
def submit_flag(
    slug: str, payload: SubmitRequest, db: Session = Depends(get_db)
) -> SubmitResponse:
    row = progress.get_challenge_row(db, slug)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Challenge not found")

    progress.ensure_player(db, payload.player_id)
    correct = flags.verify_flag(payload.flag, row.flag_hash)

    db.add(
        Submission(
            player_id=payload.player_id,
            challenge_id=row.id,
            submitted_flag=payload.flag[:300],
            is_correct=correct,
        )
    )

    already_solved = progress.is_solved(db, payload.player_id, row.id)
    newly_solved = False
    if correct and not already_solved:
        from ..models import Solve

        db.add(Solve(player_id=payload.player_id, challenge_id=row.id))
        newly_solved = True

    db.commit()

    logger.info(
        "submit player=%s challenge=%s correct=%s newly_solved=%s",
        payload.player_id,
        slug,
        correct,
        newly_solved,
    )

    if correct and already_solved:
        return SubmitResponse(
            correct=True, solved=True, message="Challenge already solved."
        )
    if correct:
        return SubmitResponse(
            correct=True, solved=True, message="Challenge solved."
        )
    return SubmitResponse(
        correct=False, solved=already_solved, message="Incorrect flag."
    )
