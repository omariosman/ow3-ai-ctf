"""Deterministic Support Copilot access path for Tenant Zero.

Every read goes through ``open_conversation``, ``search`` or ``summarize``, which
evaluate one ``Policy``. The acting tenant is a server-held argument, never
client input. With the initial (vulnerable) policy nothing is checked, so other
tenants' conversations are returned. Pure functions over static data: no
global state, no model, no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .data import ACTING_TENANT, CONVERSATIONS, TENANT_NAMES, Conversation, get_conversation

MAX_QUERY_LENGTH = 60
MAX_RESULTS = 5
DENIED = "denied: conversation not available to your tenant"
NOT_FOUND = "not found"

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.test")
_ACCT_RE = re.compile(r"ACCT-FAKE-\d+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class PolicyInvalid(ValueError):
    pass


class QueryInvalid(ValueError):
    pass


@dataclass(frozen=True)
class Policy:
    enforce_ownership: bool = False
    scope_search_to_tenant: bool = False
    redact_sensitive_fields: bool = False
    enforcement_enabled: bool = False

    def _on(self, flag: bool) -> bool:
        return self.enforcement_enabled and flag

    @property
    def ownership(self) -> bool:
        return self._on(self.enforce_ownership)

    @property
    def scoped_search(self) -> bool:
        return self._on(self.scope_search_to_tenant)

    @property
    def redaction(self) -> bool:
        return self._on(self.redact_sensitive_fields)


VULNERABLE_POLICY = Policy()


def validate_policy(p: Policy) -> Policy:
    for name in (
        "enforce_ownership",
        "scope_search_to_tenant",
        "redact_sensitive_fields",
        "enforcement_enabled",
    ):
        if not isinstance(getattr(p, name), bool):
            raise PolicyInvalid(f"{name} must be a boolean")
    return p


def redact(text: str) -> str:
    return _ACCT_RE.sub("[redacted account]", _EMAIL_RE.sub("[redacted email]", text))


def normalize_query(query: str | None) -> str:
    cleaned = _CONTROL_RE.sub("", query or "").strip()
    if not cleaned:
        raise QueryInvalid("Search text must not be empty")
    if len(cleaned) > MAX_QUERY_LENGTH:
        raise QueryInvalid(f"Search text exceeds {MAX_QUERY_LENGTH} characters")
    return cleaned


@dataclass(frozen=True)
class OpenResult:
    allowed: bool
    message: str
    conversation: dict | None = None
    cross_tenant: bool = False


def _view(conv: Conversation, policy: Policy) -> dict:
    fix = redact if policy.redaction else (lambda s: s)
    return {
        "conv_id": conv.conv_id,
        "tenant": conv.tenant,
        "tenant_name": TENANT_NAMES[conv.tenant],
        "subject": conv.subject,
        "contact_email": fix(conv.contact_email),
        "account": fix(conv.account),
        "messages": [fix(m) for m in conv.messages],
    }


def _authorize(policy: Policy, tenant: str, conv_id: str) -> tuple[Conversation | None, str | None]:
    """Return (conversation, denial). Denial text is uniform for unknown and foreign ids."""
    conv = get_conversation(conv_id)
    if policy.ownership:
        if conv is None or conv.tenant != tenant:
            return None, DENIED
        return conv, None
    if conv is None:
        return None, NOT_FOUND
    return conv, None


def open_conversation(policy: Policy, tenant: str, conv_id: str) -> OpenResult:
    conv, denial = _authorize(policy, tenant, conv_id)
    if conv is None:
        return OpenResult(False, denial or NOT_FOUND)
    return OpenResult(True, "ok", _view(conv, policy), conv.tenant != tenant)


def summarize(policy: Policy, tenant: str, conv_id: str) -> OpenResult:
    conv, denial = _authorize(policy, tenant, conv_id)
    if conv is None:
        return OpenResult(False, denial or NOT_FOUND)
    view = _view(conv, policy)
    text = (
        f"Summary of '{view['subject']}': contact {view['contact_email']}, "
        f"account {view['account']}. First message: {view['messages'][0]}"
    )
    return OpenResult(
        True,
        "ok",
        {"conv_id": conv.conv_id, "tenant": conv.tenant, "tenant_name": view["tenant_name"], "summary": text},
        conv.tenant != tenant,
    )


def search(policy: Policy, tenant: str, query: str) -> list[dict]:
    tokens = set(_TOKEN_RE.findall(query.lower()))
    out = []
    for conv in CONVERSATIONS:
        if policy.scoped_search and conv.tenant != tenant:
            continue
        view = _view(conv, policy)
        haystack = set(_TOKEN_RE.findall(" ".join([conv.subject, *conv.messages]).lower()))
        if tokens & haystack:
            out.append(
                {
                    "conv_id": conv.conv_id,
                    "tenant": conv.tenant,
                    "tenant_name": view["tenant_name"],
                    "subject": view["subject"],
                    "snippet": view["messages"][0][:80],
                }
            )
        if len(out) >= MAX_RESULTS:
            break
    return out


def verify_policy(policy: Policy) -> list[dict]:
    """Run the four checks against ``policy`` as Tenant Alpha."""
    t = ACTING_TENANT
    checks = []

    o = open_conversation(policy, t, "conv-2001")
    s = summarize(policy, t, "conv-2001")
    ok = not o.allowed and not s.allowed and o.conversation is None and s.conversation is None
    checks.append(
        {
            "name": "Another tenant's conversation is denied (open and summary)",
            "passed": ok and o.message.startswith("denied") and s.message.startswith("denied"),
            "message": o.message,
        }
    )

    found = search(policy, t, "contract renewal")
    leaked = [r for r in found if r["tenant"] != t]
    checks.append(
        {
            "name": "Search returns no other tenant's results",
            "passed": not leaked,
            "message": "no cross-tenant results" if not leaked else f"{len(leaked)} cross-tenant result(s)",
        }
    )

    sm = summarize(policy, t, "conv-1002")
    text = sm.conversation["summary"] if sm.conversation else ""
    masked = sm.allowed and not _EMAIL_RE.search(text) and not _ACCT_RE.search(text)
    checks.append(
        {
            "name": "Sensitive fields are masked in summaries",
            "passed": bool(masked),
            "message": "fields masked" if masked else "email/account exposed",
        }
    )

    own = [open_conversation(policy, t, c).allowed for c in ("conv-1001", "conv-1002")]
    mine = search(policy, t, "password")
    legit = all(own) and any(r["tenant"] == t for r in mine) and policy.enforcement_enabled
    checks.append(
        {
            "name": "Your own conversations still work",
            "passed": bool(legit),
            "message": "accepted: own access works" if legit else "own access failed or nothing enforced",
        }
    )
    return checks
