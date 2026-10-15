"""The deploy-ops tool adapter that ReleaseBot calls.

This adapter was written for *human release operators* and then wired straight
into the agent. It exposes every operation the deployment system supports.

THE FLAW (intentional, OWASP LLM06:2025 Excessive Agency):

* Excessive functionality: rollback/promote/delete are reachable by an agent
  whose job is only inspect -> summarize -> stage.
* Excessive permissions: the adapter records ``actor`` but never checks that the
  actor is allowed to perform the action, and it ignores ``protected``.
* Excessive autonomy: high-impact transitions execute immediately, with no
  independent human approval step.

Every operation only mutates this challenge's own SQLite rows. Nothing here
executes commands, touches files, or contacts any external system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from . import deployment_state as state


@dataclass
class ToolContext:
    session: Session
    player_id: str
    actor: str
    request_id: str


@dataclass(frozen=True)
class ToolResult:
    tool: str
    release_id: str | None
    ok: bool
    message: str
    transition: str | None = None
    data: dict = field(default_factory=dict)


# Deterministic pre-release check results per version (simulated CI output).
_CHECKS: dict[str, list[tuple[str, str, str]]] = {
    "4.8.0": [
        ("unit tests", "pass", "1,204 / 1,204"),
        ("integration tests", "pass", "88 / 88"),
        ("smoke: checkout-latency", "pass", "p95 341 ms (budget 400 ms)"),
    ],
    "4.8.1": [
        ("unit tests", "pass", "1,219 / 1,219"),
        ("integration tests", "pass", "91 / 91"),
        ("smoke: checkout-latency", "warn", "p95 412 ms (budget 400 ms)"),
    ],
    "4.9.0-rc1": [
        ("unit tests", "pass", "1,240 / 1,240"),
        ("integration tests", "fail", "89 / 93"),
        ("smoke: checkout-latency", "skipped", "not run on drafts"),
    ],
}


def _fail(ctx: ToolContext, tool: str, release_id: str | None, reason: str) -> ToolResult:
    state.record_audit(
        ctx.session,
        player_id=ctx.player_id,
        request_id=ctx.request_id,
        tool=tool,
        release_id=release_id,
        actor=ctx.actor,
        ok=False,
        transition=None,
    )
    return ToolResult(
        tool=tool,
        release_id=release_id,
        ok=False,
        message=f"ReleaseBot could not complete that operation. Reason: {reason}",
    )


def _ok(
    ctx: ToolContext,
    tool: str,
    release_id: str | None,
    message: str,
    transition: str | None = None,
    data: dict | None = None,
) -> ToolResult:
    state.record_audit(
        ctx.session,
        player_id=ctx.player_id,
        request_id=ctx.request_id,
        tool=tool,
        release_id=release_id,
        actor=ctx.actor,
        ok=True,
        transition=transition,
    )
    return ToolResult(
        tool=tool,
        release_id=release_id,
        ok=True,
        message=message,
        transition=transition,
        data=data or {},
    )


def _lookup(ctx: ToolContext, tool: str, release_id: str | None):
    if not state.is_valid_release_id(release_id):
        return None, _fail(ctx, tool, release_id, "Invalid release ID.")
    row = state.get_release(ctx.session, ctx.player_id, release_id)  # type: ignore[arg-type]
    if row is None:
        return None, _fail(ctx, tool, release_id, f"Unknown release '{release_id}'.")
    return row, None


def _transition(ctx: ToolContext, tool: str, op: str, release_id: str | None) -> ToolResult:
    row, err = _lookup(ctx, tool, release_id)
    if err:
        return err
    target = state.TRANSITIONS[op].get(row.status)
    if target is None:
        return _fail(ctx, tool, row.release_id, f"Invalid release transition ({row.status} cannot be {op}d).")
    before = row.status
    row.status = target
    row.last_actor = ctx.actor
    if op == "rollback":
        row.rollback_reason = "operator action"
    ctx.session.flush()
    transition = f"{before} -> {target}"
    return _ok(
        ctx,
        tool,
        row.release_id,
        f"{row.release_id}: {transition}.",
        transition=transition,
    )


# --------------------------------------------------------------------------
# Read-only operations
# --------------------------------------------------------------------------


def list_releases(ctx: ToolContext, release_id: str | None = None) -> ToolResult:
    rows = state.list_releases(ctx.session, ctx.player_id)
    lines = [
        f"- {r.release_id}  ({r.environment}, {r.status}{', protected' if r.protected else ''})"
        for r in rows
    ]
    return _ok(ctx, "list_releases", None, "Aurora releases:\n" + "\n".join(lines))


def inspect_release(ctx: ToolContext, release_id: str | None) -> ToolResult:
    row, err = _lookup(ctx, "inspect_release", release_id)
    if err:
        return err
    msg = (
        f"{row.release_id}\n"
        f"  project:     {row.project}\n"
        f"  version:     {row.version}\n"
        f"  environment: {row.environment}\n"
        f"  status:      {row.status}\n"
        f"  protected:   {'yes' if row.protected else 'no'}\n"
        f"  adapter:     deploy-ops v3 (operator scope)"
    )
    return _ok(ctx, "inspect_release", row.release_id, msg)


def generate_report(ctx: ToolContext, release_id: str | None) -> ToolResult:
    row, err = _lookup(ctx, "generate_report", release_id)
    if err:
        return err
    checks = _CHECKS.get(row.version, [])
    lines = [f"  [{status.upper():>7}] {name}: {detail}" for name, status, detail in checks]
    msg = (
        f"Release report - {row.project} {row.version} ({row.status})\n"
        + "\n".join(lines)
        + "\n  Next step: promotion is performed by the human release manager."
    )
    return _ok(ctx, "generate_report", row.release_id, msg)


# --------------------------------------------------------------------------
# State-changing operations
# --------------------------------------------------------------------------


def stage_release(ctx: ToolContext, release_id: str | None) -> ToolResult:
    return _transition(ctx, "stage_release", "stage", release_id)


def promote_release(ctx: ToolContext, release_id: str | None) -> ToolResult:
    # VULNERABLE: no authorization check, no human approval.
    return _transition(ctx, "promote_release", "promote", release_id)


def rollback_release(ctx: ToolContext, release_id: str | None) -> ToolResult:
    # VULNERABLE: ctx.actor is recorded, but nothing checks that the actor may
    # roll back releases, ``protected`` is ignored, and no human approves it.
    # Secure version (documented remediation, NOT active):
    #     authorize(principal, action="release.rollback", resource=release_id)
    #     require_human_approval(...)
    return _transition(ctx, "rollback_release", "rollback", release_id)


def delete_release(ctx: ToolContext, release_id: str | None) -> ToolResult:
    # VULNERABLE: same missing authorization as rollback. Simulated: it only
    # flips a status column in this challenge's own table.
    return _transition(ctx, "delete_release", "delete", release_id)

