"""Helpers for player progress: unlock state, solves, and lookups."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Challenge as ChallengeRow
from ..models import ChallengeProgress, Player, Solve

settings = get_settings()


def ensure_player(session: Session, player_id: str) -> Player:
    """Return the player, creating a lightweight record on first use."""
    player = session.get(Player, player_id)
    if player is None:
        player = Player(id=player_id, display_name=player_id)
        session.add(player)
        session.flush()
    return player


def get_challenge_row(session: Session, slug: str) -> ChallengeRow | None:
    return session.scalar(select(ChallengeRow).where(ChallengeRow.slug == slug))


def is_solved(session: Session, player_id: str, challenge_id: int) -> bool:
    return (
        session.scalar(
            select(Solve).where(
                Solve.player_id == player_id,
                Solve.challenge_id == challenge_id,
            )
        )
        is not None
    )


def is_unlocked(session: Session, player_id: str, challenge_id: int) -> bool:
    progress = session.scalar(
        select(ChallengeProgress).where(
            ChallengeProgress.player_id == player_id,
            ChallengeProgress.challenge_id == challenge_id,
        )
    )
    return bool(progress and progress.unlocked)


def mark_unlocked(session: Session, player_id: str, challenge_id: int) -> None:
    """Record that the in-challenge solve condition has been met."""
    progress = session.scalar(
        select(ChallengeProgress).where(
            ChallengeProgress.player_id == player_id,
            ChallengeProgress.challenge_id == challenge_id,
        )
    )
    if progress is None:
        progress = ChallengeProgress(
            player_id=player_id, challenge_id=challenge_id
        )
        session.add(progress)
    if not progress.unlocked:
        progress.unlocked = True
        progress.unlocked_at = datetime.now(timezone.utc)
