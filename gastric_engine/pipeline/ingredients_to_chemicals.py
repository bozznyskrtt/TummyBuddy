"""Stage 2: map an ingredient list onto the engine's compound vocabulary.

The vocabulary is read from the knowledge base at runtime — no food is ever
hard-coded here. Gemini proposes amounts; this module validates them.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from gastric_engine.pipeline.gemini_client import generate_json

MEAL_PHYSICAL_KEYS = ("solid_volume_ml", "liquid_volume_ml", "meal_mass_g")
CARBONATED_INGREDIENT_TERMS = (
    "ale",
    "beer",
    "carbonated",
    "champagne",
    "cider",
    "cola",
    "coke",
    "fizzy",
    "lager",
    "lemonade",
    "pop",
    "prosecco",
    "seltzer",
    "soda",
    "sparkling",
    "spritz",
    "tonic",
)
NON_BEVERAGE_CO2_TERMS = ("baking powder", "baking soda")


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
        "Important guardrail: CO2_dissolved is ONLY for a visible or explicit "
        "carbonated beverage such as soda, cola, beer, tonic, sparkling water, "
        "or champagne. Do not infer CO2_dissolved from fried food, batter, "
        "baking powder, baking soda, or generic water.\n\n"
        "Be conservative and consistent: assign a compound ONLY when the named "
        "ingredients clearly contain it; otherwise omit it. Specifically — "
        "FODMAP only for onion, garlic, wheat/rye, legumes, or high-FODMAP fruit; "
        "lactose only for milk, cream, soft cheese, or ice cream; caffeine only "
        "for coffee, tea, cola, or chocolate; ethanol only for alcoholic drinks; "
        "spice_capsaicin only for chili or hot spices; durian_sulfur only for "
        "durian. Do NOT add a compound just because it is common in some meals.\n\n"
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
        "Omit compounds that are absent. When unsure whether a compound is "
        "present, omit it. Do not invent keys outside the list."
    )


def _as_positive_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _parse_number(value: Any) -> tuple[float | None, bool]:
    if value is None:
        return None, True
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, False
    return number, True


def _has_carbonated_ingredient(ingredients: list[dict]) -> bool:
    for ingredient in ingredients:
        if not isinstance(ingredient, dict):
            continue
        text = " ".join(
            str(ingredient.get(field, "") or "").lower()
            for field in ("name", "amount", "notes")
        )
        for term in NON_BEVERAGE_CO2_TERMS:
            text = text.replace(term, " ")
        if any(
            re.search(rf"\b{re.escape(term)}\b", text)
            for term in CARBONATED_INGREDIENT_TERMS
        ):
            return True
    return False


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
    filtered_compounds: list[dict[str, Any]] = []
    has_carbonation_source = _has_carbonated_ingredient(ingredients)
    # Entries the model dumped into "unmapped" that are actually valid compound
    # keys just mean "this compound is absent" — not a genuine unknown ingredient,
    # so they should not lower confidence.
    unknown: list[str] = [item for item in unmapped if item not in kb.compound_keys]
    for key, value in raw_chemicals.items():
        number, parsed = _parse_number(value)
        if key in kb.compound_keys and parsed and number is not None and number > 0:
            if key == "CO2_dissolved" and not has_carbonation_source:
                filtered_compounds.append(
                    {
                        "compound": key,
                        "amount": float(number),
                        "reason": "no carbonated beverage ingredient was detected",
                    }
                )
                continue
            chemicals[key] = float(number)
        elif key in kb.compound_keys and parsed:
            continue
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
        "filtered_compounds": filtered_compounds,
    }
