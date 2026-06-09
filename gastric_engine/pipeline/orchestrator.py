"""Run image -> ingredients -> chemicals -> simulation as one call."""

from __future__ import annotations

from typing import Any, Callable

from gastric_engine.api.routes import simulate_endpoint
from gastric_engine.knowledge_base.loader import load_knowledge_base
from gastric_engine.pipeline.image_to_ingredients import predict_food_and_ingredients
from gastric_engine.pipeline.ingredients_to_chemicals import map_ingredients_to_chemicals


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
    if bridge_stage is None:
        kb = load_knowledge_base()
        bridge_stage = lambda ingredients: map_ingredients_to_chemicals(ingredients, kb)

    recipe = image_stage(image)
    bridge = bridge_stage(recipe.get("ingredients", []))

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

    result["dish"] = recipe.get("dish", "unknown dish")
    result["ingredients"] = recipe.get("ingredients", [])
    result["chemicals"] = bridge["chemicals"]
    result["meal_physical"] = bridge["meal_physical"]
    return result
