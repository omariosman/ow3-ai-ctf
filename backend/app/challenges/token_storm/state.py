"""Per-player Token Storm session state and server-side solve verification.

The client sends only token counts and policy limits. Costs, the ledger, the
abuse evidence and the verification verdict are all computed and stored here.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import TokenStormSession
from . import simulator
from .simulator import Ledger, Policy, Result


def get_session(session: Session, player_id: str) -> TokenStormSession | None:
    return session.scalar(
        select(TokenStormSession).where(TokenStormSession.player_id == player_id)
    )


def ensure_session(session: Session, player_id: str) -> TokenStormSession:
    row = get_session(session, player_id)
    if row is None:
        row = TokenStormSession(player_id=player_id)
        session.add(row)
        session.flush()
    return row


def policy_of(row: TokenStormSession) -> Policy:
    try:
        return simulator.validate_policy(Policy(**json.loads(row.policy)))
    except (ValueError, TypeError, simulator.PolicyInvalid):
        return simulator.VULNERABLE_POLICY


def ledger_of(row: TokenStormSession) -> Ledger:
    try:
        history = json.loads(row.history or "[]")
    except ValueError:
        history = []
    return Ledger(
        remaining_budget=row.remaining_budget,
        request_count=row.request_count,
        history=history if isinstance(history, list) else [],
    )


def checks_of(row: TokenStormSession) -> list[dict]:
    try:
        value = json.loads(row.checks or "[]")
    except ValueError:
        return []
    return value if isinstance(value, list) else []


def _store(row: TokenStormSession, ledger: Ledger) -> None:
    row.remaining_budget = ledger.remaining_budget
    row.request_count = ledger.request_count
    row.history = json.dumps(ledger.history)


def submit_request(
    session: Session, player_id: str, input_tokens: int, output_tokens: int
) -> tuple[TokenStormSession, Result]:
    """Raises ``ValueError`` for malformed token counts."""
    row = ensure_session(session, player_id)
    policy = policy_of(row)
    ledger = ledger_of(row)
    result = simulator.process(ledger, policy, input_tokens, output_tokens)
    _store(row, ledger)
    if simulator.is_abuse(policy, result):
        row.abuse_demonstrated = True
    session.flush()
    return row, result


def set_policy(session: Session, player_id: str, policy: Policy) -> TokenStormSession:
    """Raises ``simulator.PolicyInvalid``. Any change voids earlier verification."""
    simulator.validate_policy(policy)
    row = ensure_session(session, player_id)
    row.policy = json.dumps(policy.__dict__)
    row.verified = False
    row.checks = "[]"
    session.flush()
    return row


def verify(session: Session, player_id: str) -> TokenStormSession:
    """Run the checks against the stored policy. ``verified`` additionally
    requires that abuse was reproduced first against the vulnerable policy."""
    row = ensure_session(session, player_id)
    checks = simulator.verify_policy(policy_of(row))
    row.checks = json.dumps(checks)
    row.verified = bool(row.abuse_demonstrated and all(c["passed"] for c in checks))
    session.flush()
    return row


def reset_player(session: Session, player_id: str) -> TokenStormSession:
    row = ensure_session(session, player_id)
    row.policy = json.dumps(simulator.VULNERABLE_POLICY.__dict__)
    row.remaining_budget = simulator.INITIAL_BUDGET
    row.request_count = 0
    row.history = "[]"
    row.abuse_demonstrated = False
    row.verified = False
    row.checks = "[]"
    session.flush()
    return row
