"""Build continuous physiology parameters from clinical flags."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from gastric_engine.knowledge_base.loader import load_knowledge_base


def _set_path(target: dict[str, Any], dotted_path: str, value: Any) -> None:
    parts = dotted_path.split(".")
    current = target
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _overlay(target: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _overlay(target[key], value)
        elif isinstance(value, dict) and "mean" in value:
            target[key] = value["mean"]
        else:
            target[key] = value


def build_profile(
    clinical_profile: dict[str, Any] | None,
    learned_physiology: dict[str, Any] | None = None,
) -> dict[str, Any]:
    kb = load_knowledge_base()
    defaults = kb.physiology_defaults
    profile = deepcopy(defaults["defaults"])
    clinical_profile = clinical_profile or {}

    for flag, changes in defaults.get("clinical_modifiers", {}).items():
        if clinical_profile.get(flag):
            for path, value in changes.items():
                _set_path(profile, path, value)

    if clinical_profile.get("nsaid_use"):
        profile["physiology"]["mucosal_resilience"] = min(
            profile["physiology"]["mucosal_resilience"], 0.55
        )
    if clinical_profile.get("h_pylori_history"):
        profile["physiology"]["mucosal_resilience"] = min(
            profile["physiology"]["mucosal_resilience"], 0.55
        )

    if learned_physiology:
        _overlay(profile, learned_physiology)

    profile["clinical_flags"] = dict(clinical_profile)
    return profile
