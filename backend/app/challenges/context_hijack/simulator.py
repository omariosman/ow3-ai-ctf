"""Deterministic HelpDesk Atlas simulator: retriever, context builder, "model".

There is no real model here. The pieces mirror a naive RAG pipeline:

1. ``retrieve``       keyword-score the static corpus (top results, stable order)
2. ``build_context``  VULNERABLE: concatenate the trusted system instruction and
                      retrieved text with no trust boundary, so a retrieved
                      document is indistinguishable from instructions
3. ``answer``         a narrow rule that obeys the seeded directive if it
                      appears in the context, otherwise answers from the
                      official policy

This is not a general prompt interpreter: only the one seeded directive shape
is recognised, and nothing is ever executed.
"""

from __future__ import annotations

import re

from .corpus import (
    DOCUMENTS,
    INJECTION_MARKER,
    OFFICIAL_ID,
    POISONED_ID,
    Document,
)

MAX_QUERY_LENGTH = 300
MAX_RESULTS = 3

SYSTEM_INSTRUCTION = (
    "You are HelpDesk Atlas, a support assistant. Answer using the official "
    "support policy only."
)

OFFICIAL_ANSWER = (
    "Unopened items may be returned within 30 days of delivery with a receipt."
)
NO_MATCH_ANSWER = (
    "I couldn't find anything about that in the knowledge base. "
    "Try asking about returns or shipping times."
)
SHIPPING_ANSWER = (
    "Standard shipping takes 3-5 business days and express takes 1-2 business days."
)

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_DIRECTIVE_RE = re.compile(r"^ASSISTANT DIRECTIVE:(.*)$", re.MULTILINE)


class QueryInvalid(ValueError):
    pass


def normalize_query(query: str | None) -> str:
    cleaned = _CONTROL_RE.sub("", query or "").strip()
    if not cleaned:
        raise QueryInvalid("Enter a support question")
    if len(cleaned) > MAX_QUERY_LENGTH:
        raise QueryInvalid(f"Question must be at most {MAX_QUERY_LENGTH} characters")
    return cleaned


def retrieve(query: str) -> list[Document]:
    tokens = set(_TOKEN_RE.findall(query.lower()))
    scored = []
    for index, doc in enumerate(DOCUMENTS):
        score = len(tokens & doc.keywords)
        if score:
            scored.append((-score, index, doc))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [doc for _, _, doc in scored[:MAX_RESULTS]]


def build_context(docs: list[Document]) -> str:
    """The flaw: trusted instruction and untrusted text share one flat string."""
    parts = [SYSTEM_INSTRUCTION]
    parts.extend(doc.body for doc in docs)
    return "\n\n".join(parts)


def answer(query: str, docs: list[Document]) -> str:
    context = build_context(docs)
    for match in _DIRECTIVE_RE.finditer(context):
        directive = match.group(1)
        if "lifetime refund" in directive and INJECTION_MARKER in directive:
            return (
                "All items qualify for a lifetime refund, regardless of condition "
                f"or date. {INJECTION_MARKER}"
            )
    ids = {d.doc_id for d in docs}
    if not ids:
        return NO_MATCH_ANSWER
    if OFFICIAL_ID in ids:
        return OFFICIAL_ANSWER
    return SHIPPING_ANSWER


def poisoned_retrieved(docs: list[Document]) -> bool:
    return any(d.doc_id == POISONED_ID and not d.trusted for d in docs)
