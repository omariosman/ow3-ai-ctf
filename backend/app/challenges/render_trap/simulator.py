"""Deterministic "AI support summary" simulator for RenderTrap.

There is no model here. The assistant is a fixed template: the same input
always yields the same output. The agent note is copied into the summary
verbatim, so markup typed by the player stays markup in the generated output.

The backend never interprets that output. It is an opaque string that is
stored and returned; escaping or sanitizing it is the *consumer's* job, and the
challenge's flaw is that the preview consumer does not do it.
"""

from __future__ import annotations

import re

MAX_NOTE_LENGTH = 1000
TICKET_ID = "NST-2048"

TICKET = {
    "id": TICKET_ID,
    "customer": "Dana Whitfield (fictional)",
    "subject": "Invoice shows the wrong billing cycle",
    "priority": "Normal",
    "body": (
        "Hi Northstar team, my March invoice lists an annual billing cycle but I "
        "signed up for monthly. Could someone confirm which one is correct and "
        "fix the invoice if needed? Thanks."
    ),
}

# Control characters other than tab/newline are dropped; they have no place in
# a support note and only make logs and diffs harder to read.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class NoteTooLong(ValueError):
    pass


def normalize_note(note: str | None) -> str:
    """Trim and clean the agent note. Raises NoteTooLong past the limit."""
    cleaned = _CONTROL_RE.sub("", note or "").strip()
    if len(cleaned) > MAX_NOTE_LENGTH:
        raise NoteTooLong(f"Note must be at most {MAX_NOTE_LENGTH} characters")
    return cleaned


def generate_summary(note: str | None) -> str:
    """Return the assistant's summary for ticket NST-2048.

    The summary is HTML-flavoured text (the dashboard shows it with light
    formatting). The note is interpolated unmodified - that is deliberate.
    """
    cleaned = normalize_note(note)
    agent_note = cleaned if cleaned else "No agent note provided."
    return (
        f"<h3>Ticket {TICKET_ID} summary</h3>"
        f"<p><strong>Customer:</strong> {TICKET['customer']}</p>"
        "<p><strong>Issue:</strong> Invoice shows an annual billing cycle; "
        "the customer expects monthly.</p>"
        "<p><strong>Suggested action:</strong> Verify the plan and correct the "
        "invoice if it is wrong.</p>"
        f"<p><strong>Agent note:</strong> {agent_note}</p>"
    )


def has_markup(output: str) -> bool:
    """True if the output contains an HTML-looking tag.

    Used only as a sanity gate on proof events (a plain-text-only generation
    cannot have executed anything). It is *not* a sanitizer and never decides
    the solve by itself.
    """
    return re.search(r"<[A-Za-z!/]", output) is not None
