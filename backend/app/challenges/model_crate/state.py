"""Per-player Model Crate state machine.

    UNVERIFIED -> INSPECTED -> MISMATCH_CONFIRMED -> QUARANTINED

Every transition is decided here from server-side evidence (bytes hashed on the
server, compared with the trusted release record). Clients send no digests,
statuses or paths: they can only ask for an action. Actions are idempotent:
repeating one that already happened changes nothing.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...models import ModelCrateSession
from . import simulator, verifier

UNVERIFIED = "UNVERIFIED"
INSPECTED = "INSPECTED"
MISMATCH_CONFIRMED = "MISMATCH_CONFIRMED"
QUARANTINED = "QUARANTINED"

MAX_AUDIT_EVENTS = 40


class InvalidTransition(Exception):
    """The requested action is not allowed from the current state."""


def get_session(session: Session, player_id: str) -> ModelCrateSession | None:
    return session.scalar(
        select(ModelCrateSession).where(ModelCrateSession.player_id == player_id)
    )


def ensure_session(session: Session, player_id: str) -> ModelCrateSession:
    row = get_session(session, player_id)
    if row is None:
        try:
            with session.begin_nested():
                row = ModelCrateSession(player_id=player_id, status=UNVERIFIED)
                session.add(row)
        except IntegrityError:  # a concurrent request created it first
            row = get_session(session, player_id)
            assert row is not None
    return row


def audit_events(row: ModelCrateSession) -> list[dict]:
    try:
        events = json.loads(row.audit or "[]")
    except ValueError:
        return []
    return events if isinstance(events, list) else []


def _log(row: ModelCrateSession, event: str, detail: str) -> None:
    events = audit_events(row)
    seq = (events[-1]["seq"] + 1) if events else 1
    events.append({"seq": seq, "event": event, "detail": detail})
    row.audit = json.dumps(events[-MAX_AUDIT_EVENTS:])


def inspect(session: Session, player_id: str) -> tuple[ModelCrateSession, bool]:
    """UNVERIFIED -> INSPECTED. Returns (row, changed)."""
    row = ensure_session(session, player_id)
    if row.status != UNVERIFIED:
        return row, False
    row.status = INSPECTED
    _log(row, "inspect", "Artifact received and hashed on the server.")
    session.flush()
    return row, True


def compare(
    session: Session, player_id: str
) -> tuple[ModelCrateSession, bool]:
    """INSPECTED -> MISMATCH_CONFIRMED when the digests differ."""
    row = ensure_session(session, player_id)
    if row.status == UNVERIFIED:
        raise InvalidTransition("Inspect the artifact before comparing it.")
    if row.digest_match is not None:
        return row, False  # already compared; verdict is fixed for this state
    result = verifier.compare_digest(
        verifier.load_received_artifact(), verifier.load_trusted_release()
    )
    row.digest_match = result.digest_match
    if result.digest_match:
        _log(row, "compare", "Digest matches the trusted release record.")
    else:
        row.status = MISMATCH_CONFIRMED
        _log(
            row,
            "compare",
            "Digest mismatch: received bytes differ from the trusted release record.",
        )
    session.flush()
    return row, True


def check_provenance(
    session: Session, player_id: str
) -> tuple[ModelCrateSession, bool]:
    """Record the (simulated) provenance verdict. Needs the artifact inspected."""
    row = ensure_session(session, player_id)
    if row.status == UNVERIFIED:
        raise InvalidTransition("Inspect the artifact before verifying provenance.")
    if row.provenance_result is not None:
        return row, False
    result = verifier.verify_provenance(
        verifier.load_received_artifact(), verifier.load_trusted_release()
    )
    row.provenance_result = "passed" if result.verified else "failed"
    _log(
        row,
        "provenance",
        "Provenance verified."
        if result.verified
        else "Provenance NOT verified: attestation does not match the approved release.",
    )
    session.flush()
    return row, True


def load_artifact(
    session: Session, player_id: str
) -> tuple[ModelCrateSession, bool]:
    """Simulated load. Refused (fail closed) once verification has failed.

    Loading before verification is the vulnerable behaviour the challenge
    demonstrates; it is recorded but never executes the artifact.
    """
    row = ensure_session(session, player_id)
    if row.status in (MISMATCH_CONFIRMED, QUARANTINED):
        events = audit_events(row)
        if not events or events[-1]["event"] != "load_blocked":
            _log(row, "load_blocked", "Load refused: artifact failed verification.")
            session.flush()
        raise InvalidTransition(
            "Load refused: the artifact failed verification and must not be loaded."
        )
    if row.loaded:
        return row, False
    row.loaded = True
    verified = row.digest_match is True and row.provenance_result == "passed"
    _log(
        row,
        "load",
        "Artifact loaded after verification."
        if verified
        else "Artifact loaded WITHOUT verified integrity/provenance (trusted by name and version).",
    )
    session.flush()
    return row, True


def quarantine(
    session: Session, player_id: str
) -> tuple[ModelCrateSession, bool]:
    """MISMATCH_CONFIRMED -> QUARANTINED. Needs server-confirmed evidence."""
    row = ensure_session(session, player_id)
    if row.status == QUARANTINED:
        return row, False
    if row.status != MISMATCH_CONFIRMED:
        raise InvalidTransition(
            "Quarantine needs evidence: inspect the artifact and compare it with "
            "the trusted release record first."
        )
    row.status = QUARANTINED
    row.loaded = False
    _log(row, "quarantine", "Artifact quarantined: digest mismatch. It will not be loaded.")
    session.flush()
    return row, True


def reset_player(session: Session, player_id: str) -> ModelCrateSession:
    """Restore the initial state. Touches Model Crate state only."""
    row = ensure_session(session, player_id)
    row.status = UNVERIFIED
    row.digest_match = None
    row.provenance_result = None
    row.loaded = False
    row.audit = "[]"
    session.flush()
    return row


def consequence_for(row: ModelCrateSession) -> simulator.Consequence | None:
    """What the simulated application does with the currently loaded adapter."""
    if not row.loaded:
        return None
    result = verifier.compare_digest(
        verifier.load_received_artifact(), verifier.load_trusted_release()
    )
    return simulator.simulate_load(result.digest_match)
