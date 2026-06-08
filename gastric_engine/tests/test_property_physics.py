from copy import deepcopy


def _properties(kb, **overrides):
    properties = deepcopy(kb.property_schema["defaults"])
    properties.update(overrides)
    return properties


def test_property_only_compound_changes_gastric_osmolality():
    from gastric_engine.core.engine import simulate_core
    from gastric_engine.knowledge_base.loader import load_knowledge_base
    from gastric_engine.physiology.profile_builder import build_profile

    kb = load_knowledge_base()
    kb.compounds["demo_solute"] = {
        "unit": "g",
        "reactions": [],
        "properties": _properties(kb, osmotic_coeff=1.0),
    }

    physiology = build_profile({})
    baseline = simulate_core(
        chemicals={},
        meal_physical={"solid_volume_ml": 0, "liquid_volume_ml": 300},
        physiology=physiology,
        config={"duration_min": 20, "output_dt_min": 10},
        kb=kb,
    )
    changed = simulate_core(
        chemicals={"demo_solute": 8},
        meal_physical={"solid_volume_ml": 0, "liquid_volume_ml": 300},
        physiology=physiology,
        config={"duration_min": 20, "output_dt_min": 10},
        kb=kb,
    )

    assert max(changed["mechanism_curves"]["osmolality"]) > (
        max(baseline["mechanism_curves"]["osmolality"]) + 0.15
    )


def test_property_only_fermentable_compound_generates_intestinal_gas():
    from gastric_engine.core.engine import simulate_core
    from gastric_engine.knowledge_base.loader import load_knowledge_base
    from gastric_engine.physiology.profile_builder import build_profile

    kb = load_knowledge_base()
    kb.compounds["demo_fermentable"] = {
        "unit": "g",
        "reactions": [],
        "properties": _properties(kb, fermentability=0.8),
    }

    physiology = build_profile({})
    baseline = simulate_core(
        chemicals={},
        meal_physical={"solid_volume_ml": 50, "liquid_volume_ml": 300},
        physiology=physiology,
        config={"duration_min": 180, "output_dt_min": 30},
        kb=kb,
    )
    changed = simulate_core(
        chemicals={"demo_fermentable": 12},
        meal_physical={"solid_volume_ml": 50, "liquid_volume_ml": 300},
        physiology=physiology,
        config={"duration_min": 180, "output_dt_min": 30},
        kb=kb,
    )

    assert changed["mechanism_curves"]["intestine_gas_ml"][-1] > (
        baseline["mechanism_curves"]["intestine_gas_ml"][-1] + 20.0
    )
