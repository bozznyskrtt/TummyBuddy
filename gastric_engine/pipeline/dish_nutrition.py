"""Dish -> nutrition -> chemicals grounding.

The previous bridge asked the vision model to estimate *grams of each engine
compound straight from pixels*, which is wildly inconsistent run-to-run (the same
"fish and chips" came back as fat 18 / 40 / 120 and FODMAP 1 / 15). Identifying
the dish is reliable; "fish and chips macros" is a stable fact. So we:

  1. take the already-identified dish name (+ visible ingredients as context),
  2. ask a text model for standard per-serving nutrition at temperature 0,
  3. map that nutrition onto engine compounds with a DETERMINISTIC function.

Only step 2 touches an LLM, and it is anchored on the dish *identity*, so the
chemistry is far more stable. Step 3 is pure and unit-tested.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from gastric_engine.pipeline.gemini_client import generate_json

NUTRITION_PROMPT = (
    "You are a nutrition reference. Give the typical nutrition for ONE standard "
    "served portion of the dish named below, using well-known reference values "
    "for that NAMED dish. Base it on the dish identity, not on guessing from a "
    "photo; the ingredient list is only context. Be realistic and consistent.\n\n"
    "Dish: {dish}\n"
    "Visible ingredients: {ingredients}\n\n"
    "Respond strictly as raw JSON (no markdown) with exactly these keys:\n"
    "{{\n"
    '  "serving_mass_g": <number>, "liquid_ml": <number>,\n'
    '  "fat_g": <number>, "protein_g": <number>, "carb_g": <number>,\n'
    '  "sugar_g": <number>, "fiber_g": <number>,\n'
    '  "FODMAP_g": <number>, "lactose_g": <number>, "caffeine_mg": <number>,\n'
    '  "alcohol_g": <number>, "acid_load": <0-1>, "capsaicin": <0-1>,\n'
    '  "carbonated": <true|false>\n'
    "}}\n"
    "Values must be physically consistent for ONE serving: fat_g + protein_g + "
    "carb_g must not exceed serving_mass_g, and use realistic per-serving amounts "
    "(protein is rarely above 60 g, fat rarely above 120 g).\n"
    "Guidance: FODMAP_g is grams of fermentable FODMAP carbohydrate — usually 0-4 "
    "for most dishes, only high for onion/garlic/wheat/rye/legume-heavy dishes "
    "(battered fried food is low, ~1-2). lactose_g only for milk/cream/soft "
    "cheese/ice cream. caffeine_mg only for coffee/tea/cola/chocolate. alcohol_g "
    "only for alcoholic drinks. acid_load and capsaicin are 0-1 intensities. Use "
    "0 (or false) when a component is absent; do not omit keys."
)


def estimate_nutrition(
    dish: str,
    ingredients: list[dict],
    *,
    generate: Callable[..., Any] = generate_json,
) -> dict:
    names = ", ".join(str(i.get("name", "")).strip() for i in ingredients if i.get("name"))
    prompt = NUTRITION_PROMPT.format(dish=dish or "unknown dish", ingredients=names or "n/a")
    result = generate(prompt)
    if not isinstance(result, dict):
        raise ValueError(f"Nutrition stage expected a JSON object, got: {result!r}")
    return result


def _num(value: Any) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return 0.0
    return n if n > 0 else 0.0


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def nutrition_to_chemicals(nutrition: dict, kb) -> dict:
    """Deterministically map a standard nutrition profile onto engine compounds.

    Pure function (no LLM, no I/O) so it is fully unit-testable.
    """
    keys = kb.compound_keys
    chemicals: dict[str, float] = {}

    def put(name: str, value: float) -> None:
        if name in keys and value > 0:
            chemicals[name] = value

    carb = _num(nutrition.get("carb_g"))
    sugar = _num(nutrition.get("sugar_g"))
    fiber = _num(nutrition.get("fiber_g"))
    # Complex carbohydrate left after sugars and fiber are removed.
    starch = max(0.0, carb - sugar - fiber)

    put("fat", _num(nutrition.get("fat_g")))
    put("protein", _num(nutrition.get("protein_g")))
    put("fiber", fiber)
    put("starch", starch)
    put("FODMAP", _num(nutrition.get("FODMAP_g")))
    put("lactose", _num(nutrition.get("lactose_g")))
    put("caffeine", _num(nutrition.get("caffeine_mg")))
    put("ethanol", _num(nutrition.get("alcohol_g")))
    put("acid_load", _clamp01(_num(nutrition.get("acid_load"))))
    put("spice_capsaicin", _clamp01(_num(nutrition.get("capsaicin"))))
    if nutrition.get("carbonated") in (True, "true", "True", 1):
        put("CO2_dissolved", 2.0)

    mass = _num(nutrition.get("serving_mass_g"))
    liquid = _num(nutrition.get("liquid_ml"))
    meal_physical: dict[str, float] = {}
    if mass > 0:
        meal_physical["meal_mass_g"] = mass
    solid = max(0.0, mass - liquid)
    if solid > 0:
        meal_physical["solid_volume_ml"] = solid  # approx density 1 g/ml
    if liquid > 0:
        meal_physical["liquid_volume_ml"] = liquid

    return {"chemicals": chemicals, "meal_physical": meal_physical, "unknown_compounds": []}


def bridge_via_nutrition(
    dish: str,
    ingredients: list[dict],
    kb,
    *,
    generate: Callable[..., Any] = generate_json,
) -> dict:
    """Dish (+ingredients) -> nutrition -> chemicals, as a bridge_stage."""
    nutrition = estimate_nutrition(dish, ingredients, generate=generate)
    bridge = nutrition_to_chemicals(nutrition, kb)
    bridge["nutrition"] = nutrition
    return bridge
