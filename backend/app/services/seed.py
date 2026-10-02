"""Idempotent database seeding (plan Phase 2).

Seeds the default local player and upserts each registered challenge's public
metadata. On first sight of a challenge it generates a flag, stores the plaintext
in the server-only flag store, and persists only the SHA-256 hash.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Challenge as ChallengeRow
from ..models import Player
from . import flag_store, flags
from .registry import all_challenges

settings = get_settings()


def _ensure_default_player(session: Session) -> None:
    existing = session.get(Player, settings.default_player_id)
    if existing is None:
        session.add(
            Player(
                id=settings.default_player_id,
                display_name=settings.default_player_name,
            )
        )


def _ensure_flag(session: Session, slug: str, row: ChallengeRow) -> None:
    """Make sure a plaintext flag + matching hash exist for the challenge."""
    plaintext = flag_store.load_flag(slug)
    if plaintext is None:
        plaintext = flags.generate_flag()
        flag_store.store_flag(slug, plaintext)
    row.flag_hash = flags.hash_flag(plaintext)


def seed_all(session: Session) -> None:
    _ensure_default_player(session)

    for challenge in all_challenges():
        meta = challenge.get_public_metadata()
        row = session.scalar(
            select(ChallengeRow).where(ChallengeRow.slug == meta.slug)
        )
        if row is None:
            row = ChallengeRow(slug=meta.slug)
            session.add(row)

        row.title = meta.title
        row.description = meta.description
        row.category = meta.category
        row.difficulty = meta.difficulty
        row.points = meta.points
        row.author = meta.author
        row.is_active = True
        _ensure_flag(session, meta.slug, row)
