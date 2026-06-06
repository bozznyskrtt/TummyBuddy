"""Load the JSON knowledge base used by the general simulation loop."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any


KB_DIR = Path(__file__).resolve().parent


@dataclass
class KnowledgeBase:
    compounds: dict[str, dict[str, Any]]
    reactions: dict[str, dict[str, Any]]
    interactions: list[dict[str, Any]]
    physiology_defaults: dict[str, Any]

    @property
    def compound_keys(self) -> set[str]:
        return {key for key in self.compounds if not key.startswith("_")}


def _load_json(name: str) -> Any:
    with (KB_DIR / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_knowledge_base() -> KnowledgeBase:
    return KnowledgeBase(
        compounds=deepcopy(_load_json("compounds.json")),
        reactions=deepcopy(_load_json("reactions.json")),
        interactions=deepcopy(_load_json("interactions.json")),
        physiology_defaults=deepcopy(_load_json("physiology_defaults.json")),
    )
