"""Minimal challenge interface (plan section 4 / Phase 4).

Intentionally small: the first challenge determines what abstraction is actually
needed. Every challenge exposes static identity, public metadata, and the static
hints. Challenge-specific interactive endpoints (such as Model Mirror's oracle)
live in their own route module and talk to the challenge's own code directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Hint:
    order: int
    cost: int
    text: str


@dataclass(frozen=True)
class ChallengeMeta:
    slug: str
    title: str
    category: str
    difficulty: str
    points: int
    author: str
    description: str
    learning_objectives: list[str] = field(default_factory=list)
    hints: list[Hint] = field(default_factory=list)


class Challenge:
    """Base class for a registered challenge."""

    meta: ChallengeMeta

    def get_public_metadata(self) -> ChallengeMeta:
        """Public, secret-free metadata shown to players."""
        return self.meta
