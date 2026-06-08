import math
from copy import deepcopy

import pytest


def sample_request(**overrides):
    request = {
        "chemicals": {
            "protein": 42,
            "fat": 55,
            "starch": 60,
            "lactose": 18,
            "FODMAP": 4,
            "caffeine": 60,
            "ethanol": 0,
            "CO2_dissolved": 2.1,
            "acid_load": 0.75,
            "spice_capsaicin": 0.15,
            "durian_sulfur": 0,
        },
        "meal_physical": {
            "solid_volume_ml": 650,
            "liquid_volume_ml": 700,
            "meal_mass_g": 950,
        },
        "clinical_profile": {
            "reflux_gord": True,
            "gastritis_history": True,
            "ulcer_history": False,
            "lactose_intolerance": True,
            "nsaid_use": False,
            "h_pylori_history": False,
        },
        "learned_physiology": {
            "enzyme_levels": {"lactase_Vmax": 0.15},
            "symptom_thresholds": {"reflux_pressure_threshold": 0.68},
        },
        "symptoms_reported": {
            "blood_in_vomit": False,
            "black_stool": False,
        },
        "simulation_config": {
            "duration_min": 360,
            "output_dt_min": 10,
        },
    }
    request.update(overrides)
    return request


def test_health_and_contract_response_shape():
    from gastric_engine.api.routes import health, simulate_endpoint

    assert health() == {"status": "ok"}

    response = simulate_endpoint(sample_request())

    assert set(response) >= {
        "summary",
        "symptom_curves",
        "mechanism_curves",
        "root_causes",
        "unknown_compounds",
        "safety_flags",
    }
    assert response["summary"]["main_symptom"] in {
        "reflux",
        "bloating",
        "diarrhea",
        "upper_pain",
        "none",
    }
    assert len(response["symptom_curves"]["time_min"]) == 37
    assert response["mechanism_curves"]["gastric_pressure"]


def test_liquid_emptying_half_life_is_about_20_minutes():
    from gastric_engine.core.engine import simulate_core
    from gastric_engine.physiology.profile_builder import build_profile

    physiology = build_profile({})
    result = simulate_core(
        chemicals={},
        meal_physical={"solid_volume_ml": 0, "liquid_volume_ml": 500},
        physiology=physiology,
        config={"duration_min": 80, "output_dt_min": 5},
    )

    time = result["mechanism_curves"]["time_min"]
    volume = result["mechanism_curves"]["volume_ml"]
    assert all(a >= b for a, b in zip(volume, volume[1:]))

    initial = volume[0]
    half_index = next(i for i, value in enumerate(volume) if value <= initial / 2)
    assert 15 <= time[half_index] <= 25


def test_new_compound_row_applies_property_vector_without_engine_change():
    from gastric_engine.core.engine import simulate_core
    from gastric_engine.knowledge_base.loader import load_knowledge_base
    from gastric_engine.physiology.profile_builder import build_profile

    kb = load_knowledge_base()
    properties = deepcopy(kb.property_schema["defaults"])
    properties["osmotic_coeff"] = 1.0
    kb.compounds["demo_solute"] = {
        "unit": "g",
        "reactions": [],
        "properties": properties,
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
        chemicals={"demo_solute": 5},
        meal_physical={"solid_volume_ml": 0, "liquid_volume_ml": 300},
        physiology=physiology,
        config={"duration_min": 20, "output_dt_min": 10},
        kb=kb,
    )

    assert max(changed["mechanism_curves"]["osmolality"]) > (
        max(baseline["mechanism_curves"]["osmolality"]) + 0.1
    )


def test_coke_meal_has_higher_pressure_than_salad_and_gas_decays():
    from gastric_engine.core.engine import simulate_core
    from gastric_engine.physiology.profile_builder import build_profile

    physiology = build_profile({"reflux_gord": True})
    coke_meal = simulate_core(
        chemicals={"CO2_dissolved": 2.1, "fat": 55, "caffeine": 60},
        meal_physical={"solid_volume_ml": 650, "liquid_volume_ml": 700},
        physiology=physiology,
        config={"duration_min": 120, "output_dt_min": 10},
    )
    salad = simulate_core(
        chemicals={"fiber": 8},
        meal_physical={"solid_volume_ml": 300, "liquid_volume_ml": 300},
        physiology=physiology,
        config={"duration_min": 120, "output_dt_min": 10},
    )

    coke_pressure = coke_meal["mechanism_curves"]["gastric_pressure"]
    coke_fundus = coke_meal["mechanism_curves"]["fundus_pressure"]
    coke_gas = coke_meal["mechanism_curves"]["gas_volume_ml"]

    assert max(coke_pressure) > max(salad["mechanism_curves"]["gastric_pressure"])
    assert max(coke_fundus) > max(salad["mechanism_curves"]["fundus_pressure"])
    assert max(coke_gas) > coke_gas[0]
    assert coke_gas[-1] < max(coke_gas)


def test_lactose_and_durian_beer_biochemistry_are_data_driven():
    from gastric_engine.core.engine import simulate_core
    from gastric_engine.physiology.profile_builder import build_profile

    normal = simulate_core(
        chemicals={"lactose": 18},
        meal_physical={"solid_volume_ml": 100, "liquid_volume_ml": 300},
        physiology=build_profile({}),
        config={"duration_min": 60, "output_dt_min": 10},
    )
    intolerant = simulate_core(
        chemicals={"lactose": 18},
        meal_physical={"solid_volume_ml": 100, "liquid_volume_ml": 300},
        physiology=build_profile({"lactose_intolerance": True}),
        config={"duration_min": 60, "output_dt_min": 10},
    )

    assert normal["mechanism_curves"]["lactose_remaining_g"][-1] < 1.0
    assert intolerant["mechanism_curves"]["lactose_remaining_g"][-1] > 7.0

    beer = simulate_core(
        chemicals={"ethanol": 18},
        meal_physical={"solid_volume_ml": 100, "liquid_volume_ml": 300},
        physiology=build_profile({}),
        config={"duration_min": 90, "output_dt_min": 10},
    )
    durian_beer = simulate_core(
        chemicals={"ethanol": 18, "durian_sulfur": 1},
        meal_physical={"solid_volume_ml": 100, "liquid_volume_ml": 300},
        physiology=build_profile({}),
        config={"duration_min": 90, "output_dt_min": 10},
    )

    assert durian_beer["metadata"]["active_interactions"] == ["durian_alcohol_aldh"]
    assert max(durian_beer["mechanism_curves"]["acetaldehyde_g"]) > max(
        beer["mechanism_curves"]["acetaldehyde_g"]
    )


def test_intestinal_compartment_creates_late_lactose_symptoms():
    from gastric_engine.core.engine import simulate_core
    from gastric_engine.physiology.profile_builder import build_profile

    meal = {
        "lactose": 18,
        "fat": 25,
        "FODMAP": 2,
    }
    physical = {"solid_volume_ml": 250, "liquid_volume_ml": 450}
    normal = simulate_core(
        meal,
        physical,
        build_profile({}),
        {"duration_min": 360, "output_dt_min": 30},
    )
    intolerant = simulate_core(
        meal,
        physical,
        build_profile({"lactose_intolerance": True}),
        {"duration_min": 360, "output_dt_min": 30},
    )

    assert intolerant["mechanism_curves"]["intestine_gas_ml"][-1] > (
        normal["mechanism_curves"]["intestine_gas_ml"][-1] + 20
    )
    assert intolerant["mechanism_curves"]["intestine_osmolality"][-1] > (
        normal["mechanism_curves"]["intestine_osmolality"][-1] + 0.1
    )
    assert intolerant["symptom_curves"]["diarrhea"][-1] > intolerant[
        "symptom_curves"
    ]["diarrhea"][0]


def test_symptom_curves_peak_at_expected_windows():
    from gastric_engine.core.engine import simulate_core
    from gastric_engine.physiology.profile_builder import build_profile

    coke = simulate_core(
        {"CO2_dissolved": 2.1, "caffeine": 60, "fat": 35},
        {"solid_volume_ml": 450, "liquid_volume_ml": 650},
        build_profile({"reflux_gord": True}),
        {"duration_min": 120, "output_dt_min": 10},
    )
    time = coke["symptom_curves"]["time_min"]
    reflux = coke["symptom_curves"]["reflux"]
    reflux_peak_time = time[reflux.index(max(reflux))]
    assert 20 <= reflux_peak_time <= 40

    dairy = simulate_core(
        {"lactose": 18, "FODMAP": 4},
        {"solid_volume_ml": 200, "liquid_volume_ml": 500},
        build_profile({"lactose_intolerance": True}),
        {"duration_min": 360, "output_dt_min": 30},
    )
    diarrhea = dairy["symptom_curves"]["diarrhea"]
    diarrhea_peak_time = dairy["symptom_curves"]["time_min"][
        diarrhea.index(max(diarrhea))
    ]
    assert diarrhea_peak_time >= 180


def test_counterfactual_ranks_co2_as_top_reflux_driver():
    from gastric_engine.core.engine import simulate
    from gastric_engine.physiology.profile_builder import build_profile

    result = simulate(
        chemicals={"CO2_dissolved": 2.1, "caffeine": 60, "fat": 35},
        meal_physical={"solid_volume_ml": 450, "liquid_volume_ml": 650},
        physiology=build_profile({"reflux_gord": True}),
        config={"duration_min": 120, "output_dt_min": 10},
    )

    drivers = result["root_causes"]["reflux"]["drivers"]
    assert drivers[0]["chemical"] == "CO2_dissolved"
    assert math.isclose(sum(d["contribution"] for d in drivers), 1.0, abs_tol=0.05)
    assert result["root_causes"]["reflux"]["advice"]


def test_bayesian_learning_lowers_lactase_and_next_prediction_risk_rises():
    from gastric_engine.core.engine import simulate_core
    from gastric_engine.physiology.learning import update_posterior_from_meal_logs
    from gastric_engine.physiology.profile_builder import build_profile

    prior = {
        "enzyme_levels": {
            "lactase_Vmax": {"mean": 0.8, "variance": 0.2},
        }
    }
    logs = [
        {"chemicals": {"lactose": 15}, "symptoms_reported": {"diarrhea": True}},
        {"chemicals": {"lactose": 18}, "symptoms_reported": {"diarrhea": True}},
        {"chemicals": {"lactose": 12}, "symptoms_reported": {"diarrhea": True}},
    ]
    posterior = update_posterior_from_meal_logs(prior, logs)

    assert posterior["enzyme_levels"]["lactase_Vmax"]["mean"] < 0.8
    assert posterior["enzyme_levels"]["lactase_Vmax"]["variance"] < 0.2

    before = simulate_core(
        {"lactose": 18},
        {"solid_volume_ml": 100, "liquid_volume_ml": 400},
        build_profile({}, learned_physiology={"enzyme_levels": {"lactase_Vmax": 0.8}}),
        {"duration_min": 360, "output_dt_min": 30},
    )
    after = simulate_core(
        {"lactose": 18},
        {"solid_volume_ml": 100, "liquid_volume_ml": 400},
        build_profile(
            {},
            learned_physiology={
                "enzyme_levels": {
                    "lactase_Vmax": posterior["enzyme_levels"]["lactase_Vmax"][
                        "mean"
                    ]
                }
            },
        ),
        {"duration_min": 360, "output_dt_min": 30},
    )

    assert max(after["symptom_curves"]["diarrhea"]) > max(
        before["symptom_curves"]["diarrhea"]
    )


def test_safety_and_characterized_compounds_affect_response(tmp_path, monkeypatch):
    from gastric_engine.api.routes import simulate_endpoint

    monkeypatch.setenv(
        "GASTRIC_ENGINE_CHARACTERIZATION_CACHE",
        str(tmp_path / "characterization_cache.json"),
    )
    response = simulate_endpoint(
        sample_request(
            chemicals={"CO2_dissolved": 1.2, "mystery_extract": 5},
            symptoms_reported={"blood_in_vomit": True, "black_stool": False},
        )
    )

    assert response["unknown_compounds"] == []
    assert response["metadata"]["low_confidence_substances"] == ["mystery_extract"]
    assert response["summary"]["confidence"] == "low"
    assert response["safety_flags"][0]["urgency"] == "urgent"
