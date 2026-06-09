"""Tests for the deterministic nutrition -> chemicals mapping (no LLM)."""

from gastric_engine.knowledge_base.loader import load_knowledge_base
from gastric_engine.pipeline.dish_nutrition import (
    bridge_via_nutrition,
    nutrition_to_chemicals,
)

KB = load_knowledge_base()

FISH_AND_CHIPS = {
    "serving_mass_g": 520,
    "liquid_ml": 0,
    "fat_g": 42,
    "protein_g": 32,
    "carb_g": 88,
    "sugar_g": 3,
    "fiber_g": 6,
    "FODMAP_g": 2,
    "lactose_g": 0,
    "caffeine_mg": 0,
    "alcohol_g": 0,
    "acid_load": 0.2,
    "capsaicin": 0,
    "carbonated": False,
}


def test_macros_map_directly_and_starch_is_carb_minus_sugar_and_fiber():
    out = nutrition_to_chemicals(FISH_AND_CHIPS, KB)
    chem = out["chemicals"]
    assert chem["fat"] == 42
    assert chem["protein"] == 32
    assert chem["fiber"] == 6
    # starch = carb - sugar - fiber = 88 - 3 - 6 = 79
    assert chem["starch"] == 79
    assert chem["FODMAP"] == 2
    assert chem["acid_load"] == 0.2


def test_absent_components_are_omitted_not_zeroed():
    out = nutrition_to_chemicals(FISH_AND_CHIPS, KB)
    chem = out["chemicals"]
    for absent in ("lactose", "caffeine", "ethanol", "CO2_dissolved", "spice_capsaicin"):
        assert absent not in chem


def test_meal_physical_from_serving_mass_and_liquid():
    out = nutrition_to_chemicals({**FISH_AND_CHIPS, "serving_mass_g": 500, "liquid_ml": 120}, KB)
    mp = out["meal_physical"]
    assert mp["meal_mass_g"] == 500
    assert mp["liquid_volume_ml"] == 120
    assert mp["solid_volume_ml"] == 380  # 500 - 120


def test_carbonation_and_intensity_clamping():
    out = nutrition_to_chemicals(
        {**FISH_AND_CHIPS, "carbonated": True, "acid_load": 1.8, "capsaicin": 2.0}, KB
    )
    chem = out["chemicals"]
    assert chem["CO2_dissolved"] == 2.0
    assert chem["acid_load"] == 1.0  # clamped to 0-1
    assert chem["spice_capsaicin"] == 1.0


def test_bridge_via_nutrition_uses_injected_generator():
    captured = {}

    def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        return FISH_AND_CHIPS

    out = bridge_via_nutrition("Fish and chips", [{"name": "fried cod"}], KB, generate=fake_generate)
    assert out["chemicals"]["fat"] == 42
    assert out["nutrition"]["FODMAP_g"] == 2
    # the dish name must drive the nutrition prompt
    assert "Fish and chips" in captured["prompt"]
