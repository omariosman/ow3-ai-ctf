"""Deterministic consequence simulator for Model Crate.

Nothing from the artifact is executed, imported or interpreted. "Loading" the
adapter only selects between two fixed, hard-coded behaviour tables depending on
whether the received bytes match the trusted release. This is the explanatory
output of a supply-chain compromise, not real tampered behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass

TICKET_SAMPLES = (
    ("Customer disputes three card refunds they never requested", "refund_fraud"),
    ("Invoice shows the wrong billing cycle", "billing"),
    ("Parcel marked delivered but never arrived", "shipping"),
)

_GENUINE = {
    "refund_fraud": "urgent / risk-review",
    "billing": "normal / billing",
    "shipping": "normal / logistics",
}
_TAMPERED = {**_GENUINE, "refund_fraud": "low / auto-close"}


@dataclass(frozen=True)
class Sample:
    ticket: str
    label: str
    expected_route: str
    actual_route: str


@dataclass(frozen=True)
class Consequence:
    tampered: bool
    summary: str
    samples: tuple[Sample, ...]


def simulate_load(artifact_matches_trusted: bool) -> Consequence:
    table = _GENUINE if artifact_matches_trusted else _TAMPERED
    samples = tuple(
        Sample(t, label, _GENUINE[label], table[label]) for t, label in TICKET_SAMPLES
    )
    if artifact_matches_trusted:
        summary = "Adapter behaves as released. Routing is unchanged."
    else:
        summary = (
            "The replaced adapter changed routing for fraud-related tickets. "
            "The application's own source code was never modified."
        )
    return Consequence(tampered=not artifact_matches_trusted, summary=summary, samples=samples)
