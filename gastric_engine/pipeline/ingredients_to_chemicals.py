"""Stage 2: map an ingredient list onto the engine's compound vocabulary.

The vocabulary is read from the knowledge base at runtime — no food is ever
hard-coded here. Gemini proposes amounts; this module validates them.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from gastric_engine.pipeline.gemini_client import generate_json

MEAL_PHYSICAL_KEYS = ("solid_volume_ml", "liquid_volume_ml", "meal_mass_g")


def build_bridge_prompt(ingredients: list[dict], kb) -> str:
    lines = []
    for key in sorted(kb.compound_keys):
        row = kb.compounds.get(key, {})
        desc = row.get("description") or row.get("_doc") or ""
        lines.append(f"- {key}: {desc}".rstrip())
    vocab = "\n".join(lines)
    ingredient_json = json.dumps(ingredients, ensure_ascii=False)
    return (
        "You convert a recipe's ingredients into a fixed set of physiological "
        "compounds for a gastric simulator. For the whole single-serving meal, "
        "estimate the TOTAL amount of each compound below. Units: grams for "
        "masses, mg for caffeine, 0-1 scale for acid_load / spice_capsaicin / "
        "durian_sulfur. Only use compounds from this list:\n"
        f"{vocab}\n\n"
        "Also estimate meal_physical: solid_volume_ml, liquid_volume_ml, "
        "meal_mass_g.\n\n"
        f"Ingredients:\n{ingredient_json}\n\n"
        "Respond strictly as raw JSON (no markdown) matching:\n"
        "{\n"
        '  "chemicals": {"<compound>": <number>, ...},\n'
        '  "meal_physical": {"solid_volume_ml": <n>, "liquid_volume_ml": <n>, '
        '"meal_mass_g": <n>},\n'
        '  "unmapped": ["<ingredient the list could not represent>", ...]\n'
        "}\n"
        "Omit compounds that are absent. Do not invent keys outside the list."
    )


def _as_positive_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def map_ingredients_to_chemicals(
    ingredients: list[dict],
    kb,
    *,
    generate: Callable[..., Any] = generate_json,
) -> dict:
    prompt = build_bridge_prompt(ingredients, kb)
    raw = generate(prompt)

    raw_chemicals = raw.get("chemicals", {}) if isinstance(raw, dict) else {}
    raw_physical = raw.get("meal_physical", {}) if isinstance(raw, dict) else {}
    unmapped = list(raw.get("unmapped", []) or []) if isinstance(raw, dict) else []

    chemicals: dict[str, float] = {}
    unknown: list[str] = list(unmapped)
    for key, value in raw_chemicals.items():
        number = _as_positive_number(value)
        if key in kb.compound_keys and number is not None:
            chemicals[key] = number
        elif key not in kb.compound_keys:
            unknown.append(key)
        else:
            # key is valid but value is not a positive number — report as unknown
            unknown.append(key)

    meal_physical: dict[str, float] = {}
    for key in MEAL_PHYSICAL_KEYS:
        number = _as_positive_number(raw_physical.get(key))
        if number is not None:
            meal_physical[key] = number

    return {
        "chemicals": chemicals,
        "meal_physical": meal_physical,
        "unknown_compounds": unknown,
    }
