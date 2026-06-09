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
    assert "CO2_dissolved is ONLY for a visible or explicit carbonated beverage" in prompt
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


def test_mapping_treats_zero_known_compounds_as_absent_not_unknown():
    kb = load_knowledge_base()

    def fake_generate(prompt, **kwargs):
        return {
            "chemicals": {
                "fat": 12,
                "lactose": 0,
                "durian_sulfur": None,
                "spice_capsaicin": -1,
            },
            "meal_physical": {"solid_volume_ml": 300},
            "unmapped": [],
        }

    result = map_ingredients_to_chemicals(
        [{"name": "fish and chips", "amount": "1 plate"}], kb, generate=fake_generate
    )

    assert result["chemicals"] == {"fat": 12.0}
    assert result["unknown_compounds"] == []


def test_mapping_rejects_carbonation_without_carbonated_ingredient():
    kb = load_knowledge_base()

    def fake_generate(prompt, **kwargs):
        return {
            "chemicals": {
                "fat": 35,
                "CO2_dissolved": 3.0,
            },
            "meal_physical": {"solid_volume_ml": 500, "liquid_volume_ml": 100},
            "unmapped": [],
        }

    result = map_ingredients_to_chemicals(
        [
            {"name": "fried cod fillet", "amount": "180 g"},
            {"name": "potato chips", "amount": "220 g"},
            {"name": "baking powder in batter", "amount": "0.5 tsp"},
            {"name": "baking soda in batter", "amount": "0.25 tsp"},
        ],
        kb,
        generate=fake_generate,
    )

    assert result["chemicals"] == {"fat": 35.0}
    assert result["filtered_compounds"] == [
        {
            "compound": "CO2_dissolved",
            "amount": 3.0,
            "reason": "no carbonated beverage ingredient was detected",
        }
    ]


def test_mapping_keeps_carbonation_for_carbonated_drinks():
    kb = load_knowledge_base()

    def fake_generate(prompt, **kwargs):
        return {
            "chemicals": {
                "fat": 20,
                "CO2_dissolved": 2.2,
            },
            "meal_physical": {"solid_volume_ml": 450, "liquid_volume_ml": 350},
            "unmapped": [],
        }

    result = map_ingredients_to_chemicals(
        [
            {"name": "burger", "amount": "1"},
            {"name": "cola soda", "amount": "330 ml"},
        ],
        kb,
        generate=fake_generate,
    )

    assert result["chemicals"]["CO2_dissolved"] == 2.2
    assert result["filtered_compounds"] == []


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
