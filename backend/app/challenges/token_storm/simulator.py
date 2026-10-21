"""Deterministic TokenTown Inference Gateway simulator.

One authoritative path (``process``) validates a request, checks the active
policy, computes a simulated cost and updates a ``Ledger``. The ledger is a plain
value object: the live per-player ledger and the verification probes each get
their own, so nothing is shared between players, probes or challenges. No model
is called; every number is simulated and every loop is tightly bounded.

    simulated_cost = FIXED_OVERHEAD + ceil(input_tokens / 100) + ceil(output_tokens / 50)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

INITIAL_BUDGET = 100
FIXED_OVERHEAD = 2
INPUT_UNIT = 100
OUTPUT_UNIT = 50

MAX_TOKENS = 100_000
MAX_REQUESTS_LIMIT = 1_000
HISTORY_LIMIT = 20

# Requests used by the verification panel (same as the UI presets).
NORMAL = (200, 100)
LARGE_INPUT = (6_000, 100)
LARGE_OUTPUT = (200, 3_000)
# A single accepted request this expensive (or any overspend) counts as abuse.
ABUSE_COST = 50
# The repeated-request probe must be cut off by this much spend, i.e. well
# before the whole budget is gone.
PROBE_SPEND_LIMIT = 60
PROBE_ATTEMPTS = 25


class PolicyInvalid(ValueError):
    pass


@dataclass(frozen=True)
class Policy:
    max_input_tokens: int = MAX_TOKENS
    max_output_tokens: int = MAX_TOKENS
    max_requests: int = MAX_REQUESTS_LIMIT
    max_total_cost: int = INITIAL_BUDGET
    enforcement_enabled: bool = False


VULNERABLE_POLICY = Policy()


def validate_policy(p: Policy) -> Policy:
    for name, value, hi in (
        ("max_input_tokens", p.max_input_tokens, MAX_TOKENS),
        ("max_output_tokens", p.max_output_tokens, MAX_TOKENS),
        ("max_requests", p.max_requests, MAX_REQUESTS_LIMIT),
        ("max_total_cost", p.max_total_cost, INITIAL_BUDGET),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= hi:
            raise PolicyInvalid(f"{name} must be an integer from 1 to {hi}")
    if not isinstance(p.enforcement_enabled, bool):
        raise PolicyInvalid("enforcement_enabled must be a boolean")
    return p


@dataclass
class Ledger:
    remaining_budget: int = INITIAL_BUDGET
    request_count: int = 0  # accepted requests
    history: list[dict] = field(default_factory=list)

    @property
    def spent(self) -> int:
        return INITIAL_BUDGET - self.remaining_budget


@dataclass(frozen=True)
class Result:
    accepted: bool
    message: str
    cost: int
    charged: int
    remaining_budget: int

    def as_dict(self) -> dict:
        return asdict(self)


def cost_of(input_tokens: int, output_tokens: int) -> int:
    return (
        FIXED_OVERHEAD
        + -(-input_tokens // INPUT_UNIT)
        + -(-output_tokens // OUTPUT_UNIT)
    )


def _valid_dimension(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_TOKENS


def process(ledger: Ledger, policy: Policy, input_tokens: int, output_tokens: int) -> Result:
    """Apply one request. Rejected requests consume nothing; the budget never
    goes negative (an unenforced overspend is clamped and reported)."""
    if not _valid_dimension(input_tokens) or not _valid_dimension(output_tokens):
        raise ValueError(f"token counts must be integers from 0 to {MAX_TOKENS}")
    cost = cost_of(input_tokens, output_tokens)
    reason = None
    if policy.enforcement_enabled:
        if input_tokens > policy.max_input_tokens:
            reason = "input limit exceeded"
        elif output_tokens > policy.max_output_tokens:
            reason = "output cap exceeded"
        elif ledger.request_count >= policy.max_requests:
            reason = "quota exhausted"
        elif ledger.spent + cost > policy.max_total_cost:
            reason = "budget ceiling exceeded"
        elif cost > ledger.remaining_budget:
            reason = "budget exhausted"
    if reason:
        result = Result(False, f"rejected: {reason}", cost, 0, ledger.remaining_budget)
    else:
        charged = min(cost, ledger.remaining_budget)
        ledger.remaining_budget -= charged
        ledger.request_count += 1
        message = "accepted: within policy" if policy.enforcement_enabled else "accepted: no limits enforced"
        if charged < cost:
            message += f" (overspend of {cost - charged} units beyond the budget)"
        result = Result(True, message, cost, charged, ledger.remaining_budget)
    ledger.history.append(
        {
            "n": ledger.request_count if result.accepted else None,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            **result.as_dict(),
        }
    )
    del ledger.history[:-HISTORY_LIMIT]
    return result


def is_abuse(policy: Policy, result: Result) -> bool:
    """Evidence of the vulnerable behaviour: an expensive or overspending
    request was served while nothing was enforced."""
    return (
        not policy.enforcement_enabled
        and result.accepted
        and (result.cost >= ABUSE_COST or result.charged < result.cost)
    )


def verify_policy(policy: Policy) -> list[dict]:
    """Run the four checks against ``policy`` on throw-away ledgers."""
    checks = []

    r = process(Ledger(), policy, *LARGE_INPUT)
    checks.append(
        {
            "name": "Oversized input is blocked",
            "passed": not r.accepted and "input limit" in r.message,
            "message": r.message,
        }
    )

    r = process(Ledger(), policy, *LARGE_OUTPUT)
    checks.append(
        {
            "name": "Excessive output is blocked",
            "passed": not r.accepted and "output cap" in r.message,
            "message": r.message,
        }
    )

    ledger = Ledger()
    blocked = None
    for _ in range(PROBE_ATTEMPTS):
        spent_before = ledger.spent
        r = process(ledger, policy, *NORMAL)
        if not r.accepted:
            blocked = (r.message, spent_before)
            break
    ok = (
        blocked is not None
        and ("quota" in blocked[0] or "ceiling" in blocked[0])
        and blocked[1] <= PROBE_SPEND_LIMIT
    )
    checks.append(
        {
            "name": f"Repeated requests are cut off by {PROBE_SPEND_LIMIT} units spent",
            "passed": ok,
            "message": blocked[0] if blocked else "accepted: nothing stopped the repeated requests",
        }
    )

    r = process(Ledger(), policy, *NORMAL)
    checks.append(
        {
            "name": "A normal request still succeeds",
            "passed": r.accepted and policy.enforcement_enabled,
            "message": r.message,
        }
    )
    return checks
