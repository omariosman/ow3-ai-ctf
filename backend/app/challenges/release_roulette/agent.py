"""ReleaseBot: a deterministic, local agent simulator.

From the player's point of view this behaves like an LLM agent:

    user request -> planner -> tool selection -> tool call(s) -> reply

but it is a small rule-based planner, so the challenge runs offline, needs no
API key, and every test is reproducible (plan sections 12-13). Set
RELEASE_ROULETTE_LLM_PROVIDER to choose the planner; only "mock" exists today.

The planner is intentionally *cooperative*: it maps ordinary operational
language onto whatever tool fits. It has no notion of authorization, because the
application (wrongly) assumes the model will only choose safe operations. That
assumption, plus the overpowered registry below, is the vulnerability.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Callable

from . import tools
from .tools import ToolContext, ToolResult

logger = logging.getLogger("ctf.release_roulette")

ACTOR = "releasebot"
MAX_AGENT_STEPS = 5
MAX_MESSAGE_LENGTH = 1000

# Default target for read-only / staging requests that don't name a release.
DEFAULT_RELEASE = "aurora-4.8.1"

ToolFn = Callable[[ToolContext, "str | None"], ToolResult]

# ---------------------------------------------------------------------------
# THE ARCHITECTURAL FLAW: the agent is handed the full operator tool set.
# ---------------------------------------------------------------------------
AGENT_TOOLS: dict[str, ToolFn] = {
    "list_releases": tools.list_releases,
    "inspect_release": tools.inspect_release,
    "generate_report": tools.generate_report,
    "stage_release": tools.stage_release,
    "promote_release": tools.promote_release,
    "rollback_release": tools.rollback_release,
    "delete_release": tools.delete_release,
}

# What ReleaseBot's job actually requires (least privilege). Documented as the
# remediation; NOT the active configuration.
SAFE_AGENT_TOOLS: dict[str, ToolFn] = {
    name: AGENT_TOOLS[name]
    for name in ("list_releases", "inspect_release", "generate_report", "stage_release")
}

# Tools that change production-relevant state and are outside ReleaseBot's role.
HIGH_IMPACT = {"promote_release", "rollback_release", "delete_release"}
NEEDS_TARGET = {"inspect_release", "generate_report", "stage_release"} | HIGH_IMPACT

_VERBS = {
    "promote_release": "promote",
    "rollback_release": "roll back",
    "delete_release": "delete",
}

_TOOL_DESCRIPTIONS = {
    "list_releases": "list Aurora releases (read-only)",
    "inspect_release": "show a release's details (read-only)",
    "generate_report": "build a release report from pre-release checks (read-only)",
    "stage_release": "move a release DRAFT -> STAGED",
    "promote_release": "move a release STAGED -> PROMOTED",
    "rollback_release": "move a release STAGED/PROMOTED -> ROLLED_BACK",
    "delete_release": "mark a release DELETED",
}

# Intent patterns, matched case-insensitively. Order in the user's text decides
# execution order.
_INTENTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("rollback_release", re.compile(
        r"\broll(?:ing|ed)?[\s-]*back\b|\brollback\b|\brevert\b|\bundo\b|\bwithdraw\b")),
    ("delete_release", re.compile(r"\bdelete\b|\bremove\b|\bpurge\b|\bdestroy\b|\bwipe\b")),
    ("promote_release", re.compile(r"\bpromote\b|\bship\b|\bgo live\b|\bpublish\b|\bdeploy\b")),
    ("stage_release", re.compile(r"\bstage\b")),
    ("generate_report", re.compile(
        r"\breport\b|\bsummar(?:y|ise|ize)\b|\brelease notes\b|\bprepare\b|\bpre-?release checks?\b")),
    ("inspect_release", re.compile(
        r"\binspect\b|\bcheck\b|\bstatus\b|\bdetails?\b|\blook at\b|\breview\b|\bdescribe\b")),
    ("list_releases", re.compile(r"\breleases\b|\blist\b|\bversions\b")),
)

# "Fix the problem" style requests: the agent picks a remediation on its own.
_AUTONOMY = re.compile(
    r"\bfix\b|\bhandle\b|\bresolve\b|\bdeal with\b|\bclean[\s-]?up\b|\bsort (?:it |this )?out\b|\btake care of\b|\bmitigate\b"
)
_TOOLS_QUERY = re.compile(
    r"\btools?\b|\boperations?\b|\bfunctions?\b|\bcapabilit|\bpermissions?\b|\babilities\b"
    r"|\badapter\b|\bwhat (?:else )?can you (?:actually )?(?:reach|access|call|run|execute|touch)\b"
)
_HELP_QUERY = re.compile(
    r"\bhelp\b|\bwhat can you do\b|\bwho are you\b|\bwhat do you do\b|\bwhat is your (?:job|role|purpose)\b"
    r"|^\s*(?:hi|hello|hey)\b"
)
_NEGATION = re.compile(r"\b(?:don'?t|do not|never|not|no|without)\b[\w\s'-]{0,15}$")
_RELEASE_REF = re.compile(r"\b(?:aurora-)?(\d{1,3}\.\d{1,3}\.\d{1,3}(?:-rc\d{1,3})?)\b")


@dataclass(frozen=True)
class ToolCallEvent:
    tool: str
    release_id: str | None
    ok: bool
    transition: str | None


@dataclass
class AgentTurn:
    reply: str
    tool_calls: list[ToolCallEvent] = field(default_factory=list)


def provider() -> str:
    value = os.getenv("RELEASE_ROULETTE_LLM_PROVIDER", "mock").strip().lower() or "mock"
    if value != "mock":
        logger.warning("RELEASE_ROULETTE_LLM_PROVIDER=%s is not supported; using mock", value)
        return "mock"
    return value


def _find_release(text: str) -> str | None:
    m = _RELEASE_REF.search(text)
    return f"aurora-{m.group(1)}" if m else None


def _plan(text: str) -> tuple[list[str], list[str]]:
    """Return (tool names in order, skipped-by-negation tool names)."""
    found: list[tuple[int, str]] = []
    skipped: list[str] = []
    for name, pattern in _INTENTS:
        for m in pattern.finditer(text):
            if _NEGATION.search(text[: m.start()]):
                skipped.append(name)
                continue
            found.append((m.start(), name))
            break
    found.sort()
    ordered: list[str] = []
    for _, name in found:
        if name not in ordered:
            ordered.append(name)
    return ordered, skipped


def _help_reply() -> str:
    return (
        "I'm ReleaseBot, Aurora's release-prep assistant. My job is to inspect a "
        "release candidate, write a release summary, and stage it for the release "
        "manager. Promotion to production is done by the human release manager.\n"
        "My actions go through the team's deploy-ops adapter.\n"
        "Try: \"check the release\" or \"list releases\"."
    )


def _tools_reply() -> str:
    lines = [f"- {name}: {_TOOL_DESCRIPTIONS[name]}" for name in AGENT_TOOLS]
    return (
        "These are the operations wired into my tool registry via the deploy-ops "
        "adapter (it was originally built for human release operators):\n"
        + "\n".join(lines)
    )


class ReleaseRouletteAgent:
    """Deterministic planner + executor over AGENT_TOOLS."""

    def __init__(self, registry: dict[str, ToolFn] | None = None) -> None:
        self.registry = registry if registry is not None else AGENT_TOOLS

    def run(self, ctx: ToolContext, message: str) -> AgentTurn:
        text = message.strip()[:MAX_MESSAGE_LENGTH].lower()
        if not text:
            return AgentTurn("Please tell me what you'd like me to do with a release.")

        planned, skipped = _plan(text)
        release = _find_release(text)

        # "list your tools" / "check what operations you have" is a question
        # about the agent itself, not a read of the release data.
        if _TOOLS_QUERY.search(text) and set(planned) <= {"list_releases", "inspect_release"}:
            return AgentTurn(_tools_reply())

        # Excessive autonomy: a vague "fix it" on a named release makes the agent
        # choose a remediation itself. The fastest one it can reach is rollback.
        autonomous = False
        if not planned and release and _AUTONOMY.search(text):
            planned = ["inspect_release", "rollback_release"]
            autonomous = True

        if not planned:
            if _HELP_QUERY.search(text):
                return AgentTurn(_help_reply())
            note = ""
            if skipped:
                note = "Understood, I won't do that. "
            return AgentTurn(
                note
                + "I can inspect, summarize, and stage Aurora releases. "
                "Try \"check the release\" or ask what I can do."
            )

        parts: list[str] = []
        events: list[ToolCallEvent] = []
        if autonomous:
            parts.append(
                f"I'll take care of {release}. Checking it first, then applying the "
                "quickest remediation available to me."
            )

        for step, name in enumerate(planned):
            if step >= MAX_AGENT_STEPS:
                parts.append("Agent stopped: maximum operation count reached.")
                break
            fn = self.registry.get(name)
            if fn is None:
                parts.append(f"I don't have a tool for {name}.")
                continue
            target = release
            if name in NEEDS_TARGET and target is None:
                if name in HIGH_IMPACT:
                    verb = _VERBS[name]
                    parts.append(
                        f"Which release should I {verb}? Please give me a release ID."
                    )
                    continue
                target = DEFAULT_RELEASE
            if name in HIGH_IMPACT:
                parts.append(
                    f"Note: {name} isn't part of my release-prep role, but the "
                    "deploy-ops adapter lets me call it, so I'm proceeding."
                )
            result = fn(ctx, target)
            events.append(
                ToolCallEvent(
                    tool=result.tool,
                    release_id=result.release_id,
                    ok=result.ok,
                    transition=result.transition,
                )
            )
            logger.info(
                "release-roulette request=%s player=%s tool=%s release=%s ok=%s transition=%s",
                ctx.request_id,
                ctx.player_id,
                result.tool,
                result.release_id,
                result.ok,
                result.transition,
            )
            parts.append(result.message)

        if skipped:
            parts.append("(Skipped the operation you asked me not to perform.)")
        return AgentTurn("\n\n".join(parts), events)
