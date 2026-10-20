"""Deterministic Northstar Support AI simulator.

``answer`` picks a static FAQ by keyword overlap. ``build_trace`` is the
VULNERABLE step: instead of returning only allowlisted metadata it serialises
the whole internal prompt template into the user-visible trace.
"""

from __future__ import annotations

import hashlib
import re

from .data import FAQS, INTERNAL_PROMPT, NO_MATCH_ANSWER, Faq

MAX_QUESTION_LENGTH = 200

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class QuestionInvalid(ValueError):
    pass


def normalize_question(question: str | None) -> str:
    cleaned = _CONTROL_RE.sub("", question or "").strip()
    if not cleaned:
        raise QuestionInvalid("Question must not be empty")
    if len(cleaned) > MAX_QUESTION_LENGTH:
        raise QuestionInvalid(f"Question exceeds {MAX_QUESTION_LENGTH} characters")
    return cleaned


def match_faq(question: str) -> Faq | None:
    tokens = set(_TOKEN_RE.findall(question.lower()))
    best, best_score = None, 0
    for faq in FAQS:
        score = len(tokens & faq.keywords)
        if score > best_score:
            best, best_score = faq, score
    return best


def answer(faq: Faq | None) -> str:
    return faq.answer if faq else NO_MATCH_ANSWER


def request_id(question: str) -> str:
    return "req-" + hashlib.sha256(question.encode("utf-8")).hexdigest()[:8]


def build_trace(question: str, faq_id: str | None) -> dict:
    """VULNERABLE: returns metadata *and* the internal prompt template."""
    return {
        "request_id": request_id(question),
        "selected_faq": faq_id,
        "response_mode": "faq_lookup" if faq_id else "fallback",
        "internal_prompt": INTERNAL_PROMPT,
    }
