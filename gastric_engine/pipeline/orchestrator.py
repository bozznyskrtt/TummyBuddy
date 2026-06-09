"""Run image -> ingredients -> chemicals -> simulation as one call."""

from __future__ import annotations

from typing import Any, Callable

from gastric_engine.api.routes import simulate_endpoint
from gastric_engine.knowledge_base.loader import load_knowledge_base
from gastric_engine.pipeline.dish_nutrition import bridge_via_nutrition
from gastric_engine.pipeline.image_to_ingredients import predict_food_and_ingredients
from gastric_engine.pipeline.ingredients_to_chemicals import map_ingredients_to_chemicals


def _default_bridge(dish: str, ingredients: list, kb) -> dict:
    """Dish -> nutrition -> chemicals, falling back to the raw ingredient bridge.

    The nutrition path anchors chemistry on the dish identity (stable). If the
    nutrition LLM call fails or returns garbage, fall back to estimating compounds
    straight from the ingredient list so a forecast is still produced.
    """
    try:
        return bridge_via_nutrition(dish, ingredients, kb)
    except Exception:  # noqa: BLE001 -- resilience: any failure -> fallback bridge
        return map_ingredients_to_chemicals(ingredients, kb)


def analyze_meal(
    image: Any,
    *,
    clinical_profile: dict | None = None,
    learned_physiology: dict | None = None,
    symptoms_reported: dict | None = None,
    simulation_config: dict | None = None,
    image_stage: Callable[[Any], dict] | None = None,
    bridge_stage: Callable[[list], dict] | None = None,
) -> dict:
    image_stage = image_stage or predict_food_and_ingredients

    recipe = image_stage(image)
    dish = recipe.get("dish", "unknown dish")
    ingredients = recipe.get("ingredients", [])

    if bridge_stage is None:
        bridge = _default_bridge(dish, ingredients, load_knowledge_base())
    else:
        # Injected bridges keep the original (ingredients -> bridge) contract.
        bridge = bridge_stage(ingredients)

    result = simulate_endpoint(
        {
            "chemicals": bridge["chemicals"],
            "meal_physical": bridge["meal_physical"],
            "clinical_profile": clinical_profile or {},
            "learned_physiology": learned_physiology,
            "symptoms_reported": symptoms_reported,
            "simulation_config": simulation_config,
        }
    )

    merged_unknown = list(
        dict.fromkeys(
            [*result.get("unknown_compounds", []), *bridge.get("unknown_compounds", [])]
        )
    )
    result["unknown_compounds"] = merged_unknown
    if merged_unknown:
        result["summary"]["confidence"] = "low"

    filtered_compounds = bridge.get("filtered_compounds", [])
    if filtered_compounds:
        result.setdefault("metadata", {})["filtered_compounds"] = filtered_compounds

    result["dish"] = dish
    result["ingredients"] = ingredients
    result["chemicals"] = bridge["chemicals"]
    result["meal_physical"] = bridge["meal_physical"]
    if bridge.get("nutrition"):
        result["nutrition"] = bridge["nutrition"]
    return result
