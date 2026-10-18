"""SQLAlchemy ORM models for the platform data model (plan section 9)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(80), default="")
    difficulty: Mapped[str] = mapped_column(String(40), default="")
    points: Mapped[int] = mapped_column(Integer, default=0)
    author: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # SHA-256 hex digest of the flag. The plaintext flag is never stored.
    flag_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="challenge", cascade="all, delete-orphan"
    )
    solves: Mapped[list["Solve"]] = relationship(
        back_populates="challenge", cascade="all, delete-orphan"
    )


class Player(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), default="Player")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), index=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), index=True)
    submitted_flag: Mapped[str] = mapped_column(String(300))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    challenge: Mapped[Challenge] = relationship(back_populates="submissions")


class Solve(Base):
    __tablename__ = "solves"
    __table_args__ = (
        UniqueConstraint("player_id", "challenge_id", name="uq_player_challenge"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), index=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), index=True)
    solved_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    challenge: Mapped[Challenge] = relationship(back_populates="solves")


class ChallengeProgress(Base):
    """Per-player, per-challenge progress state.

    This holds the deterministic "unlocked" flag set by a challenge validator
    once the in-challenge solve condition is met (plan section 15). It is the
    bridge between reaching the intended model behavior and being allowed to
    retrieve/submit the flag.
    """

    __tablename__ = "challenge_progress"
    __table_args__ = (
        UniqueConstraint("player_id", "challenge_id", name="uq_progress"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), index=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), index=True)
    unlocked: Mapped[bool] = mapped_column(Boolean, default=False)
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Release Roulette (challenge-specific, additive tables).
#
# The simulated deployment database for the Release Roulette challenge. Scoped
# by player so every player gets an isolated copy of Project Aurora. Nothing
# here ever touches real infrastructure.
# ---------------------------------------------------------------------------


class ReleaseRouletteRelease(Base):
    __tablename__ = "release_roulette_releases"
    __table_args__ = (
        UniqueConstraint("player_id", "release_id", name="uq_rr_player_release"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(String(80), index=True)
    release_id: Mapped[str] = mapped_column(String(80))
    project: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(40))
    environment: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40))
    protected: Mapped[bool] = mapped_column(Boolean, default=False)
    # Who performed the last high-impact transition, and why. Recorded by the
    # deployment adapter but never checked by it (that is the flaw).
    last_actor: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rollback_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


class ReleaseRouletteAudit(Base):
    """One row per tool invocation made through the deployment adapter."""

    __tablename__ = "release_roulette_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(String(80), index=True)
    request_id: Mapped[str] = mapped_column(String(40))
    tool: Mapped[str] = mapped_column(String(40))
    release_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    actor: Mapped[str] = mapped_column(String(80))
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    transition: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


# ---------------------------------------------------------------------------
# RenderTrap (challenge-specific, additive table).
#
# One row per player: the last assistant output, the current preview generation
# and a short-lived nonce used to tie a proof event to that exact preview.
# ---------------------------------------------------------------------------


class RenderTrapSession(Base):
    __tablename__ = "render_trap_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Monotonic: bumped on every submit and reset, never reused.
    generation: Mapped[int] = mapped_column(Integer, default=0)
    nonce: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nonce_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    proof_status: Mapped[str] = mapped_column(String(20), default="none")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


# ---------------------------------------------------------------------------
# Model Crate (challenge-specific, additive table).
#
# One row per player: the server-authoritative verification state machine for
# the received artifact, plus a small audit trail. Clients never write it.
# ---------------------------------------------------------------------------


class ModelCrateSession(Base):
    __tablename__ = "model_crate_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    # UNVERIFIED -> INSPECTED -> MISMATCH_CONFIRMED -> QUARANTINED
    status: Mapped[str] = mapped_column(String(24), default="UNVERIFIED")
    # None until compared; True/False is the server's digest verdict.
    digest_match: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # None until checked; "passed" | "failed".
    provenance_result: Mapped[str | None] = mapped_column(String(10), nullable=True)
    loaded: Mapped[bool] = mapped_column(Boolean, default=False)
    # JSON list of audit events (capped by the state module).
    audit: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )
