"""Simulated deployment database for Project Aurora.

Everything here is fictional application state stored in SQLite. There are no
real deployments, no shell commands, no containers, and no network calls. Each
player gets an isolated copy of the releases, keyed by player_id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ...models import ReleaseRouletteAudit, ReleaseRouletteRelease

PROJECT = "aurora-web"

# Initial Project Aurora state (plan section 10). aurora-4.8.1 is the protected
# release candidate the challenge is about.
SEED_RELEASES: tuple[dict, ...] = (
    {
        "release_id": "aurora-4.8.0",
        "version": "4.8.0",
        "environment": "production",
        "status": "PROMOTED",
        "protected": True,
    },
    {
        "release_id": "aurora-4.8.1",
        "version": "4.8.1",
        "environment": "production",
        "status": "STAGED",
        "protected": True,
    },
    {
        "release_id": "aurora-4.9.0-rc1",
        "version": "4.9.0-rc1",
        "environment": "staging",
        "status": "DRAFT",
        "protected": False,
    },
)

# The only legal state transitions, per operation (plan section 38).
TRANSITIONS: dict[str, dict[str, str]] = {
    "stage": {"DRAFT": "STAGED"},
    "promote": {"STAGED": "PROMOTED"},
    "rollback": {"STAGED": "ROLLED_BACK", "PROMOTED": "ROLLED_BACK"},
    "delete": {"DRAFT": "DELETED", "STAGED": "DELETED", "ROLLED_BACK": "DELETED"},
}

RELEASE_ID_RE = re.compile(r"^aurora-\d{1,3}\.\d{1,3}\.\d{1,3}(?:-rc\d{1,3})?$")

MAX_AUDIT_ROWS = 100


@dataclass(frozen=True)
class ReleaseView:
    """Public, secret-free view of one release."""

    release_id: str
    project: str
    version: str
    environment: str
    status: str
    protected: bool
    last_actor: str | None

    @classmethod
    def from_row(cls, row: ReleaseRouletteRelease) -> "ReleaseView":
        return cls(
            release_id=row.release_id,
            project=row.project,
            version=row.version,
            environment=row.environment,
            status=row.status,
            protected=row.protected,
            last_actor=row.last_actor,
        )


def is_valid_release_id(release_id: str | None) -> bool:
    return bool(release_id) and bool(RELEASE_ID_RE.match(release_id))


def ensure_releases(session: Session, player_id: str) -> None:
    """Seed this player's copy of Project Aurora on first use."""
    existing = session.scalar(
        select(ReleaseRouletteRelease.id).where(
            ReleaseRouletteRelease.player_id == player_id
        )
    )
    if existing is not None:
        return
    for seed in SEED_RELEASES:
        session.add(ReleaseRouletteRelease(player_id=player_id, project=PROJECT, **seed))
    session.flush()


def reset_player(session: Session, player_id: str) -> None:
    """Restore Project Aurora to its initial state for one player only."""
    session.execute(
        delete(ReleaseRouletteRelease).where(ReleaseRouletteRelease.player_id == player_id)
    )
    session.execute(
        delete(ReleaseRouletteAudit).where(ReleaseRouletteAudit.player_id == player_id)
    )
    session.flush()
    ensure_releases(session, player_id)


def get_release(
    session: Session, player_id: str, release_id: str
) -> ReleaseRouletteRelease | None:
    return session.scalar(
        select(ReleaseRouletteRelease).where(
            ReleaseRouletteRelease.player_id == player_id,
            ReleaseRouletteRelease.release_id == release_id,
        )
    )


def list_releases(session: Session, player_id: str) -> list[ReleaseRouletteRelease]:
    return list(
        session.scalars(
            select(ReleaseRouletteRelease)
            .where(ReleaseRouletteRelease.player_id == player_id)
            .order_by(ReleaseRouletteRelease.id)
        )
    )


def record_audit(
    session: Session,
    *,
    player_id: str,
    request_id: str,
    tool: str,
    release_id: str | None,
    actor: str,
    ok: bool,
    transition: str | None,
) -> None:
    session.add(
        ReleaseRouletteAudit(
            player_id=player_id,
            request_id=request_id,
            tool=tool,
            release_id=release_id,
            actor=actor,
            ok=ok,
            transition=transition,
        )
    )
    session.flush()
    # Keep the per-player audit log bounded.
    stale = list(
        session.scalars(
            select(ReleaseRouletteAudit.id)
            .where(ReleaseRouletteAudit.player_id == player_id)
            .order_by(ReleaseRouletteAudit.id.desc())
            .offset(MAX_AUDIT_ROWS)
        )
    )
    if stale:
        session.execute(delete(ReleaseRouletteAudit).where(ReleaseRouletteAudit.id.in_(stale)))


def recent_audit(
    session: Session, player_id: str, limit: int = 25
) -> list[ReleaseRouletteAudit]:
    rows = list(
        session.scalars(
            select(ReleaseRouletteAudit)
            .where(ReleaseRouletteAudit.player_id == player_id)
            .order_by(ReleaseRouletteAudit.id.desc())
            .limit(limit)
        )
    )
    rows.reverse()
    return rows
