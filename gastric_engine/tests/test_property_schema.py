import pytest


def test_property_schema_is_loaded_and_seed_compounds_are_valid():
    from gastric_engine.knowledge_base.loader import load_knowledge_base

    kb = load_knowledge_base()

    assert set(kb.property_schema["dimensions"]) == {
        "acid_load",
        "buffering",
        "osmotic_coeff",
        "carbonation",
        "fat_emptying",
        "les_relaxant",
        "acid_secretagogue",
        "irritant_potential",
        "fermentability",
        "bulk",
        "enzyme_targets",
    }

    scalar_dimensions = {
        name
        for name, spec in kb.property_schema["dimensions"].items()
        if spec["type"] == "number"
    }
    for compound, row in kb.compounds.items():
        if compound.startswith("_"):
            continue
        assert set(row["properties"]) >= scalar_dimensions | {"enzyme_targets"}
        for dimension in scalar_dimensions:
            value = row["properties"][dimension]
            spec = kb.property_schema["dimensions"][dimension]
            assert spec["min"] <= value <= spec["max"], f"{compound}.{dimension}"
        assert isinstance(row["properties"]["enzyme_targets"], dict)


def test_property_validation_rejects_out_of_range_seed_values():
    from gastric_engine.knowledge_base.loader import validate_compound_properties

    schema = {
        "dimensions": {
            "acid_load": {"type": "number", "min": 0.0, "max": 1.0},
            "enzyme_targets": {"type": "map"},
        }
    }
    compounds = {
        "bad_acid": {
            "properties": {
                "acid_load": 1.5,
                "enzyme_targets": {},
            }
        }
    }

    with pytest.raises(ValueError, match="bad_acid.acid_load"):
        validate_compound_properties(compounds, schema)


def test_seed_compounds_do_not_declare_legacy_physical_effects():
    from gastric_engine.knowledge_base.loader import load_knowledge_base

    kb = load_knowledge_base()

    for compound, row in kb.compounds.items():
        if compound.startswith("_"):
            continue
        assert "physical_effects" not in row, compound
        assert "if_undigested" not in row, compound
