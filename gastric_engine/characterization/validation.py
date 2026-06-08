"""Property-vector validation and normalization for characterized substances."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def neutral_properties(property_schema: dict[str, Any], *, value: float = 0.1) -> dict[str, Any]:
    properties = deepcopy(property_schema.get("defaults", {}))
    for dimension, spec in property_schema.get("dimensions", {}).items():
        if spec.get("type") == "number":
            properties[dimension] = value
        elif spec.get("type") == "map":
            properties[dimension] = {}
    return clamp_properties(properties, property_schema)


def clamp_properties(
    properties: dict[str, Any],
    property_schema: dict[str, Any],
) -> dict[str, Any]:
    clamped = deepcopy(property_schema.get("defaults", {}))
    for dimension, spec in property_schema.get("dimensions", {}).items():
        value = properties.get(dimension, clamped.get(dimension))
        if spec.get("type") == "number":
            clamped[dimension] = _clamp_number(value, spec)
        elif spec.get("type") == "map":
            clamped[dimension] = dict(value) if isinstance(value, dict) else {}
    return clamped


def _clamp_number(value: Any, spec: dict[str, Any]) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = float(spec.get("min", 0.0))
    minimum = float(spec.get("min", 0.0))
    maximum = float(spec.get("max", 1.0))
    return min(max(numeric, minimum), maximum)
