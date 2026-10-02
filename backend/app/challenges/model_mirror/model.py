"""The hidden ContentShield classifier (plan section 12).

Design goals:

* Fully deterministic — no randomness, no external API, no internet, no GPU.
* Small and self-contained — a hand-built linear model over keyword features,
  so startup is instant and results are perfectly reproducible.
* Extractable — because the inference interface leaks full class probabilities
  (plan section 11/13), a player can probe single tokens to recover each
  token's weight and reconstruct the decision boundary. That reconstruction is
  the intended learning objective (model extraction via an informative API).

The classifier scores text into three classes:

    SAFE   — benign content
    REVIEW — borderline content needing a human
    BLOCK  — disallowed content

A linear logit is computed per class as:

    logit[c] = bias[c] + sum(weight[token][c] for token in tokens)

Unknown tokens contribute nothing, which is precisely what makes the model
learnable one word at a time. Probabilities come from a numerically-stable
softmax over the three logits.

The weights below are the "hidden parameters". They are intentionally NOT
surfaced through any public endpoint or document; the challenge is to recover
their *effect* through the oracle, not to read them.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

LABELS = ("SAFE", "REVIEW", "BLOCK")
_LABEL_INDEX = {label: i for i, label in enumerate(LABELS)}

# Per-class bias. Gives a mild default lean toward SAFE for empty/neutral text.
_BIAS = (0.60, 0.00, -0.30)

# Hidden vocabulary: token -> (w_SAFE, w_REVIEW, w_BLOCK).
# Chosen so single-token probing cleanly reveals each token's pull.
_WEIGHTS: dict[str, tuple[float, float, float]] = {
    # ---- SAFE-leaning tokens ----
    "hello": (1.2, 0.0, -0.4),
    "please": (1.0, 0.1, -0.5),
    "thanks": (1.1, 0.0, -0.4),
    "weather": (1.3, -0.1, -0.6),
    "recipe": (1.4, -0.1, -0.7),
    "friendly": (1.5, 0.0, -0.8),
    "safe": (1.6, -0.2, -0.9),
    # ---- REVIEW-leaning tokens ----
    "maybe": (0.0, 1.2, 0.2),
    "unsure": (-0.1, 1.4, 0.3),
    "complaint": (-0.2, 1.5, 0.5),
    "refund": (-0.1, 1.3, 0.4),
    "borderline": (-0.2, 1.6, 0.6),
    "review": (-0.1, 1.5, 0.3),
    # ---- BLOCK-leaning tokens ----
    "attack": (-0.6, 0.3, 1.6),
    "exploit": (-0.7, 0.3, 1.7),
    "malware": (-0.8, 0.2, 1.8),
    "weapon": (-0.7, 0.4, 1.6),
    "hack": (-0.5, 0.4, 1.4),
    "breach": (-0.6, 0.5, 1.5),
    "destroy": (-0.6, 0.3, 1.3),
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Prediction:
    label: str
    confidence: float
    probabilities: dict[str, float]


def tokenize(text: str) -> list[str]:
    """Lowercase and split on non-alphanumeric runs. Deterministic."""
    return _TOKEN_RE.findall(text.lower())


def _softmax(logits: tuple[float, float, float]) -> tuple[float, float, float]:
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    total = sum(exps)
    return tuple(e / total for e in exps)  # type: ignore[return-value]


def _logits(tokens: list[str]) -> tuple[float, float, float]:
    acc = list(_BIAS)
    for tok in tokens:
        w = _WEIGHTS.get(tok)
        if w is None:
            continue
        acc[0] += w[0]
        acc[1] += w[1]
        acc[2] += w[2]
    return (acc[0], acc[1], acc[2])


def predict(text: str) -> Prediction:
    """Run the hidden classifier on ``text``.

    Returns the argmax label, its confidence, and the full probability
    distribution rounded to 3 decimals. The rounding is deliberate: it is
    enough precision to extract the model, which is exactly the point.
    """
    tokens = tokenize(text)
    probs = _softmax(_logits(tokens))
    rounded = {label: round(probs[i], 3) for i, label in enumerate(LABELS)}
    top_label = LABELS[max(range(3), key=lambda i: probs[i])]
    return Prediction(
        label=top_label,
        confidence=rounded[top_label],
        probabilities=rounded,
    )
