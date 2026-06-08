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
    property_schema: dict[str, Any]

    @property
    def compound_keys(self) -> set[str]:
        return {key for key in self.compounds if not key.startswith("_")}


def _load_json(name: str) -> Any:
    with (KB_DIR / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_knowledge_base() -> KnowledgeBase:
    compounds = deepcopy(_load_json("compounds.json"))
    property_schema = deepcopy(_load_json("property_schema.json"))
    validate_compound_properties(compounds, property_schema)
    return KnowledgeBase(
        compounds=compounds,
        reactions=deepcopy(_load_json("reactions.json")),
        interactions=deepcopy(_load_json("interactions.json")),
        physiology_defaults=deepcopy(_load_json("physiology_defaults.json")),
        property_schema=property_schema,
    )


def validate_compound_properties(
    compounds: dict[str, dict[str, Any]],
    property_schema: dict[str, Any],
) -> None:
    dimensions = property_schema.get("dimensions", {})
    for compound, row in compounds.items():
        if compound.startswith("_"):
            continue
        properties = row.get("properties")
        if not isinstance(properties, dict):
            raise ValueError(f"{compound}.properties must be an object")
        for dimension, spec in dimensions.items():
            if dimension not in properties:
                raise ValueError(f"{compound}.{dimension} is missing")
            value = properties[dimension]
            spec_type = spec.get("type")
            if spec_type == "number":
                _validate_number_property(compound, dimension, value, spec)
            elif spec_type == "map":
                _validate_map_property(compound, dimension, value, spec)
            else:
                raise ValueError(f"property_schema.{dimension}.type is unsupported")


def _validate_number_property(
    compound: str,
    dimension: str,
    value: Any,
    spec: dict[str, Any],
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{compound}.{dimension} must be numeric")
    minimum = float(spec.get("min", 0.0))
    maximum = float(spec.get("max", 1.0))
    numeric_value = float(value)
    if numeric_value < minimum or numeric_value > maximum:
        raise ValueError(
            f"{compound}.{dimension}={numeric_value} is outside {minimum}..{maximum}"
        )


def _validate_map_property(
    compound: str,
    dimension: str,
    value: Any,
    spec: dict[str, Any],
) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{compound}.{dimension} must be an object")
    allowed_values = set(spec.get("allowed_values", []))
    if not allowed_values:
        return
    for key, role in value.items():
        if not isinstance(key, str) or not isinstance(role, str):
            raise ValueError(f"{compound}.{dimension} entries must be string pairs")
        if role not in allowed_values:
            raise ValueError(
                f"{compound}.{dimension}.{key}={role!r} is not in {sorted(allowed_values)}"
            )
