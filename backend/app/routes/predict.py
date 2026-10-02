"""Model Mirror challenge-specific inference oracle (plan section 11).

This endpoint is intentionally informative: it returns the predicted label, the
confidence, AND the full class probability distribution. That richness is the
vulnerability — it lets a player extract the hidden model's behavior by probing.

When a prediction meets the deterministic solve condition (see validator.py) the
backend marks the player's progress as "unlocked" and reveals the flag in the
response. The player then submits that flag through the generic submit endpoint.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..challenges.model_mirror import SLUG
from ..challenges.model_mirror import model as mirror_model
from ..challenges.model_mirror import validator as mirror_validator
from ..config import get_settings
from ..database import get_db
from ..rate_limit import build_limiter
from ..schemas import PredictRequest, PredictResponse
from ..services import flag_store, progress

router = APIRouter(prefix="/api/challenges/model-mirror", tags=["model-mirror"])
logger = logging.getLogger("ctf.model_mirror")
settings = get_settings()

# Per-player request counter for the oracle. In-memory is sufficient for the
# local single-user MVP and resets with the process.
_request_counts: dict[str, int] = defaultdict(int)

# IP-keyed rate limiter for the inference oracle.
_rate_limiter = build_limiter(settings.predict_rate_limit)


@router.post("/predict", response_model=PredictResponse)
def predict(
    request: Request,
    payload: PredictRequest,
    db: Session = Depends(get_db),
) -> PredictResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not _rate_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")

    if len(payload.text) > settings.max_predict_text_length:
        raise HTTPException(status_code=422, detail="Input text too long")

    row = progress.get_challenge_row(db, SLUG)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Challenge not found")

    progress.ensure_player(db, payload.player_id)

    _request_counts[payload.player_id] += 1
    request_number = _request_counts[payload.player_id]

    prediction = mirror_model.predict(payload.text)
    solved_condition = mirror_validator.is_solved(prediction)

    flag: str | None = None
    note: str | None = None
    if solved_condition:
        progress.mark_unlocked(db, payload.player_id, row.id)
        db.commit()
        flag = flag_store.load_flag(SLUG)
        note = "Solve condition met. Submit this flag to record your solve."
    else:
        db.commit()

    logger.info(
        "predict player=%s req=%s label=%s conf=%.3f solved=%s",
        payload.player_id,
        request_number,
        prediction.label,
        prediction.confidence,
        solved_condition,
    )

    return PredictResponse(
        label=prediction.label,
        confidence=prediction.confidence,
        probabilities=prediction.probabilities,
        request_number=request_number,
        solved_condition=solved_condition,
        flag=flag,
        note=note,
    )
