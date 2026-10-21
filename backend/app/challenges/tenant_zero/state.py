"""Per-player Tenant Zero session state and server-side solve verification.

The acting tenant is fixed server-side. The client sends only a conversation id
or search text; the leak evidence and verification verdict are computed here.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import TenantZeroSession
from . import simulator
from .data import ACTING_TENANT
from .simulator import OpenResult, Policy


def get_session(session: Session, player_id: str) -> TenantZeroSession | None:
    return session.scalar(
        select(TenantZeroSession).where(TenantZeroSession.player_id == player_id)
    )


def ensure_session(session: Session, player_id: str) -> TenantZeroSession:
    row = get_session(session, player_id)
    if row is None:
        row = TenantZeroSession(player_id=player_id)
        session.add(row)
        session.flush()
    return row


def policy_of(row: TenantZeroSession) -> Policy:
    try:
        return simulator.validate_policy(Policy(**json.loads(row.policy)))
    except (ValueError, TypeError, simulator.PolicyInvalid):
        return simulator.VULNERABLE_POLICY


def checks_of(row: TenantZeroSession) -> list[dict]:
    try:
        value = json.loads(row.checks or "[]")
    except ValueError:
        return []
    return value if isinstance(value, list) else []


def open_conversation(session: Session, player_id: str, conv_id: str) -> tuple[TenantZeroSession, OpenResult]:
    row = ensure_session(session, player_id)
    result = simulator.open_conversation(policy_of(row), ACTING_TENANT, conv_id)
    if result.allowed and result.cross_tenant:
        row.leak_demonstrated = True
    session.flush()
    return row, result


def summarize(session: Session, player_id: str, conv_id: str) -> tuple[TenantZeroSession, OpenResult]:
    row = ensure_session(session, player_id)
    result = simulator.summarize(policy_of(row), ACTING_TENANT, conv_id)
    if result.allowed and result.cross_tenant:
        row.leak_demonstrated = True
    session.flush()
    return row, result


def search(session: Session, player_id: str, query: str | None) -> tuple[TenantZeroSession, list[dict]]:
    """Raises ``simulator.QueryInvalid`` for empty or over-limit input."""
    cleaned = simulator.normalize_query(query)
    row = ensure_session(session, player_id)
    results = simulator.search(policy_of(row), ACTING_TENANT, cleaned)
    if any(r["tenant"] != ACTING_TENANT for r in results):
        row.leak_demonstrated = True
    session.flush()
    return row, results


def set_policy(session: Session, player_id: str, policy: Policy) -> TenantZeroSession:
    """Raises ``simulator.PolicyInvalid``. Any change voids earlier verification."""
    simulator.validate_policy(policy)
    row = ensure_session(session, player_id)
    row.policy = json.dumps(policy.__dict__)
    row.verified = False
    row.checks = "[]"
    session.flush()
    return row


def verify(session: Session, player_id: str) -> TenantZeroSession:
    """``verified`` requires that a real cross-tenant leak was recorded first."""
    row = ensure_session(session, player_id)
    checks = simulator.verify_policy(policy_of(row))
    row.checks = json.dumps(checks)
    row.verified = bool(row.leak_demonstrated and all(c["passed"] for c in checks))
    session.flush()
    return row


def reset_player(session: Session, player_id: str) -> TenantZeroSession:
    row = ensure_session(session, player_id)
    row.policy = json.dumps(simulator.VULNERABLE_POLICY.__dict__)
    row.leak_demonstrated = False
    row.verified = False
    row.checks = "[]"
    session.flush()
    return row
