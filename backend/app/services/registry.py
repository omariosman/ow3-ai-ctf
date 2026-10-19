"""Challenge registry (plan Phase 2).

A single place that lists the challenges the platform knows about. Adding a new
challenge later is a matter of importing it and adding it here — the generic
platform never needs to understand a challenge's internals.
"""

from __future__ import annotations

from ..challenges.base import Challenge
from ..challenges.context_hijack import SLUG as CONTEXT_HIJACK_SLUG
from ..challenges.context_hijack import challenge as context_hijack
from ..challenges.model_crate import SLUG as MODEL_CRATE_SLUG
from ..challenges.model_crate import challenge as model_crate
from ..challenges.model_mirror import SLUG as MODEL_MIRROR_SLUG
from ..challenges.model_mirror import challenge as model_mirror
from ..challenges.render_trap import SLUG as RENDER_TRAP_SLUG
from ..challenges.render_trap import challenge as render_trap
from ..challenges.release_roulette import SLUG as RELEASE_ROULETTE_SLUG
from ..challenges.release_roulette import challenge as release_roulette

_REGISTRY: dict[str, Challenge] = {
    MODEL_MIRROR_SLUG: model_mirror,
    RELEASE_ROULETTE_SLUG: release_roulette,
    RENDER_TRAP_SLUG: render_trap,
    MODEL_CRATE_SLUG: model_crate,
    CONTEXT_HIJACK_SLUG: context_hijack,
}


def all_challenges() -> list[Challenge]:
    return list(_REGISTRY.values())


def get_challenge(slug: str) -> Challenge | None:
    return _REGISTRY.get(slug)
