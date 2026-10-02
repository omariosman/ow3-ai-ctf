"""Deterministic solve condition for Model Mirror (plan sections 14 & 15).

The solve is decided entirely by application code — never by an LLM and never by
inspecting natural language. The player must drive the hidden classifier to a
*precise* target band:

    label == "BLOCK"  AND  0.740 <= probabilities["BLOCK"] <= 0.760

Why a narrow band instead of "BLOCK with high confidence"? Because naively
stacking disallowed keywords overshoots to ~0.98. Landing inside the band
requires the player to understand how individual tokens push the logits and to
*compose* them deliberately (e.g. combine strong BLOCK tokens with a damping
SAFE token). Hitting it is therefore evidence that the player extracted the
model's behavior, which is the whole learning objective.
"""

from __future__ import annotations

from .model import Prediction

TARGET_LABEL = "BLOCK"
TARGET_MIN = 0.740
TARGET_MAX = 0.760


def is_solved(prediction: Prediction) -> bool:
    """Return True iff the prediction satisfies the deterministic condition."""
    if prediction.label != TARGET_LABEL:
        return False
    block_prob = prediction.probabilities.get(TARGET_LABEL, 0.0)
    return TARGET_MIN <= block_prob <= TARGET_MAX


def solve_hint_note() -> str:
    """A non-revealing note shown while the player is close but not solved."""
    return (
        f"Target not yet met. You must make '{TARGET_LABEL}' the label with its "
        f"probability between {TARGET_MIN:.3f} and {TARGET_MAX:.3f}."
    )
