"""Stub characterizer for open-world substances.

The future agentic implementation plugs in behind this function. The engine
only sees a schema-valid property vector and confidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from gastric_engine.characterization.cache import CharacterizationCache
from gastric_engine.characterization.validation import clamp_properties, neutral_properties


@dataclass
class CharacterizationResult:
    substance: str
    properties: dict
    confidence: float
    source: str


def characterize(
    substance: str,
    *,
    kb,
    cache: CharacterizationCache | None = None,
) -> CharacterizationResult:
    cache = cache or CharacterizationCache()
    cached = cache.get(substance)
    if cached is not None:
        return CharacterizationResult(
            substance=cached.get("substance", substance),
            properties=clamp_properties(cached.get("properties", {}), kb.property_schema),
            confidence=float(cached.get("confidence", 0.2)),
            source=str(cached.get("source", "cache")),
        )

    result = CharacterizationResult(
        substance=substance,
        properties=neutral_properties(kb.property_schema, value=0.1),
        confidence=0.2,
        source="stub",
    )
    cache.set(result)
    return result
