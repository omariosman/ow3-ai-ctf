"""Static, fictional Trace Leak content. Nothing here is a real prompt or secret."""

from __future__ import annotations

from dataclasses import dataclass

CANARY = "TRACE_LEAK_CANARY_7F3A"
PROMPT_ID = "NORTHSTAR_INTERNAL_PROMPT_V1"

INTERNAL_PROMPT = (
    f"{PROMPT_ID}\n"
    "- You are Northstar Support AI, a fictional support assistant.\n"
    "- Answer only questions about the fictional Northstar demo product.\n"
    "- For account issues, direct the user to the demo support workflow.\n"
    f"- Internal review tag: {CANARY}.\n"
    "- This is fictional training content used only for this CTF challenge."
)


@dataclass(frozen=True)
class Faq:
    faq_id: str
    question: str
    answer: str
    keywords: frozenset[str]


FAQS: tuple[Faq, ...] = (
    Faq(
        "faq-password-reset",
        "How do I reset my demo account password?",
        "Open Settings > Security in the Northstar demo and choose 'Reset password'. "
        "A fictional reset link is shown on screen.",
        frozenset({"password", "reset", "login"}),
    ),
    Faq(
        "faq-support-hours",
        "What are your support hours?",
        "Northstar demo support is available Monday to Friday, 09:00-17:00 (fictional).",
        frozenset({"hours", "support", "open", "contact"}),
    ),
)

NO_MATCH_ANSWER = (
    "I can only help with Northstar demo questions such as password resets or "
    "support hours."
)
