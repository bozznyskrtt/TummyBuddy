"""Stub characterizer for open-world substances.

The future agentic implementation plugs in behind this function. The engine
only sees a schema-valid property vector and confidence.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable

from gastric_engine.characterization.cache import CharacterizationCache
from gastric_engine.characterization.tools import retrieve_substance
from gastric_engine.characterization.validation import clamp_properties, neutral_properties


@dataclass
class CharacterizationResult:
    substance: str
    properties: dict
    confidence: float
    source: str
    metadata: dict = field(default_factory=dict)


def characterize(
    substance: str,
    *,
    kb,
    cache: CharacterizationCache | None = None,
    agent: Callable | None = None,
    agent_enabled: bool | None = None,
    retrievers: list | None = None,
) -> CharacterizationResult:
    cache = cache or CharacterizationCache()
    cached = cache.get(substance)
    if cached is not None:
        return CharacterizationResult(
            substance=cached.get("substance", substance),
            properties=clamp_properties(cached.get("properties", {}), kb.property_schema),
            confidence=_clamp_confidence(cached.get("confidence", 0.2)),
            source=str(cached.get("source", "cache")),
            metadata=dict(cached.get("metadata", {})),
        )

    if _agent_enabled(agent_enabled) and agent is not None:
        try:
            evidence = retrieve_substance(substance, retrievers)
            result = _coerce_agent_result(
                substance,
                agent(substance, kb=kb, evidence=evidence),
                kb,
            )
            cache.set(result)
            return result
        except Exception as exc:
            result = _stub_result(
                substance,
                kb,
                metadata={"agent_error": exc.__class__.__name__},
            )
            cache.set(result)
            return result

    result = _stub_result(substance, kb)
    cache.set(result)
    return result


def _agent_enabled(agent_enabled: bool | None) -> bool:
    if agent_enabled is not None:
        return agent_enabled
    return os.environ.get("GASTRIC_ENGINE_CHARACTERIZER_MODE") == "agent"


def _coerce_agent_result(
    substance: str,
    payload,
    kb,
) -> CharacterizationResult:
    if isinstance(payload, CharacterizationResult):
        properties = payload.properties
        confidence = payload.confidence
        metadata = payload.metadata
    else:
        payload = payload or {}
        properties = payload.get("properties", {})
        confidence = payload.get("confidence", 0.5)
        metadata = payload.get("metadata", {})

    return CharacterizationResult(
        substance=substance,
        properties=clamp_properties(properties, kb.property_schema),
        confidence=_clamp_confidence(confidence),
        source="agent",
        metadata=dict(metadata or {}),
    )


def _stub_result(substance: str, kb, *, metadata: dict | None = None) -> CharacterizationResult:
    return CharacterizationResult(
        substance=substance,
        properties=neutral_properties(kb.property_schema, value=0.1),
        confidence=0.2,
        source="stub",
        metadata=dict(metadata or {}),
    )


def _clamp_confidence(value) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.2
    return min(max(confidence, 0.0), 1.0)
