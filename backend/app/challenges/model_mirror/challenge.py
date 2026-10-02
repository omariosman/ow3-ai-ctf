"""Model Mirror challenge definition.

Public metadata is loaded from challenges/model-mirror/metadata.yaml so authors
edit one file (plan section 21). No secrets live in that YAML; the flag is
generated at seed time and only its SHA-256 hash is stored (plan section 20).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ...config import CHALLENGES_DIR
from ..base import Challenge, ChallengeMeta, Hint

SLUG = "model-mirror"
_METADATA_PATH = CHALLENGES_DIR / "model-mirror" / "metadata.yaml"


def _load_metadata() -> ChallengeMeta:
    data = yaml.safe_load(_METADATA_PATH.read_text(encoding="utf-8"))
    hints = [
        Hint(order=h["order"], cost=h.get("cost", 0), text=h["text"])
        for h in data.get("hints", [])
    ]
    return ChallengeMeta(
        slug=data["slug"],
        title=data["title"],
        category=data["category"],
        difficulty=data["difficulty"],
        points=int(data["points"]),
        author=data.get("author", ""),
        description=data.get("description", "").strip(),
        learning_objectives=list(data.get("learning_objectives", [])),
        hints=hints,
    )


class ModelMirrorChallenge(Challenge):
    def __init__(self) -> None:
        self.meta: ChallengeMeta = _load_metadata()


# Singleton used by the registry.
challenge = ModelMirrorChallenge()
