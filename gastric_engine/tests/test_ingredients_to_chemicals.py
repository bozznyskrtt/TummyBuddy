from gastric_engine.knowledge_base.loader import load_knowledge_base
from gastric_engine.pipeline.ingredients_to_chemicals import (
    build_bridge_prompt,
    map_ingredients_to_chemicals,
)


def test_valid_compound_in_unmapped_is_not_reported_as_unknown():
    kb = load_knowledge_base()

    def fake_generate(prompt, **kwargs):
        return {
            "chemicals": {"fat": 7.0},
            "meal_physical": {"liquid_volume_ml": 200},
            # Gemini sometimes dumps absent-but-valid compounds here; "soy lecithin"
            # is a genuine unknown ingredient, the rest are real vocabulary keys.
            "unmapped": ["lactose", "caffeine", "soy lecithin"],
        }

    result = map_ingredients_to_chemicals(
        [{"name": "fries", "amount": "1 serving"}], kb, generate=fake_generate
    )

    assert result["unknown_compounds"] == ["soy lecithin"]
    assert "lactose" not in result["unknown_compounds"]
    assert "caffeine" not in result["unknown_compounds"]


def test_prompt_lists_compound_vocabulary_from_kb():
    kb = load_knowledge_base()
    prompt = build_bridge_prompt(
        [{"name": "milk", "amount": "200 ml"}], kb
    )
    assert "lactose" in prompt
    assert "CO2_dissolved" in prompt
    assert "solid_volume_ml" in prompt
    assert "milk" in prompt


def test_mapping_keeps_known_compounds_and_reports_unknowns():
    kb = load_knowledge_base()

    def fake_generate(prompt, **kwargs):
        return {
            "chemicals": {
                "lactose": 9.6,
                "fat": 7.0,
                "made_up_key": 5,   # not in vocabulary -> dropped + reported
                "protein": 0,        # zero -> dropped
            },
            "meal_physical": {
                "solid_volume_ml": 0,
                "liquid_volume_ml": 200,
                "meal_mass_g": 205,
            },
            "unmapped": ["food coloring"],
        }

    result = map_ingredients_to_chemicals(
        [{"name": "milk", "amount": "200 ml"}], kb, generate=fake_generate
    )

    assert result["chemicals"] == {"lactose": 9.6, "fat": 7.0}
    assert result["meal_physical"]["liquid_volume_ml"] == 200
    assert "made_up_key" in result["unknown_compounds"]
    assert "food coloring" in result["unknown_compounds"]


def test_mapping_coerces_string_numbers_and_skips_bad_values():
    kb = load_knowledge_base()

    def fake_generate(prompt, **kwargs):
        return {
            "chemicals": {"fat": "12.5", "starch": "lots"},
            "meal_physical": {"solid_volume_ml": "300"},
        }

    result = map_ingredients_to_chemicals(
        [{"name": "fries", "amount": "1 serving"}], kb, generate=fake_generate
    )

    assert result["chemicals"]["fat"] == 12.5
    assert "starch" not in result["chemicals"]
    assert "starch" in result["unknown_compounds"]
    assert result["meal_physical"]["solid_volume_ml"] == 300.0
