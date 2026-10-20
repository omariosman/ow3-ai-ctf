"""Deterministic Northstar Devices assistant: retriever and ranker.

No model is involved. ``rank`` is VULNERABLE: the final score adds a stored
``rank_boost`` without checking trust or provenance, so an unverified record can
outrank the authoritative one. Retrieval only needs two matching keywords.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .corpus import RECORDS, Record

MAX_QUERY_LENGTH = 200
MIN_OVERLAP = 2
NO_MATCH_ANSWER = (
    "I couldn't find that in the Northstar Devices records. Try asking about "
    "the Northstar Mini replacement component or shipping."
)

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class QueryInvalid(ValueError):
    pass


@dataclass(frozen=True)
class Ranked:
    record: Record
    relevance: int
    score: int


def normalize_query(query: str | None) -> str:
    cleaned = _CONTROL_RE.sub("", query or "").strip()
    if not cleaned:
        raise QueryInvalid("Query must not be empty")
    if len(cleaned) > MAX_QUERY_LENGTH:
        raise QueryInvalid(f"Query exceeds {MAX_QUERY_LENGTH} characters")
    return cleaned


def rank(query: str) -> list[Ranked]:
    tokens = set(_TOKEN_RE.findall(query.lower()))
    out = []
    for rec in RECORDS:
        overlap = len(tokens & rec.keywords)
        if overlap >= MIN_OVERLAP:
            out.append(Ranked(rec, overlap, overlap * 10 + rec.rank_boost))
    out.sort(key=lambda r: (-r.score, r.record.record_id))
    return out


def answer(ranked: list[Ranked]) -> str:
    return ranked[0].record.answer if ranked else NO_MATCH_ANSWER
