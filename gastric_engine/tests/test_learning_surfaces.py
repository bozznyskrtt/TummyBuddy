def test_personal_learning_updates_multiple_enzymes_and_symptom_thresholds():
    from gastric_engine.physiology.learning import update_posterior_from_meal_logs

    prior = {
        "enzyme_levels": {
            "lactase_Vmax": {"mean": 0.8, "variance": 0.2},
            "ALDH_Vmax": {"mean": 1.0, "variance": 0.3},
        },
        "symptom_thresholds": {
            "reflux_pressure_threshold": {"mean": 0.75, "variance": 0.12},
            "pain_irritation_threshold": {"mean": 0.65, "variance": 0.10},
        },
    }
    logs = [
        {"chemicals": {"lactose": 18}, "symptoms_reported": {"diarrhea": True}},
        {"chemicals": {"lactose": 16}, "symptoms_reported": {"diarrhea": True}},
        {"chemicals": {"ethanol": 18}, "symptoms_reported": {"upper_pain": True}},
        {"chemicals": {"ethanol": 16}, "symptoms_reported": {"upper_pain": True}},
        {
            "chemicals": {"CO2_dissolved": 2.0, "caffeine": 60},
            "symptoms_reported": {"reflux": True},
        },
        {
            "chemicals": {"CO2_dissolved": 1.8, "caffeine": 40},
            "symptoms_reported": {"reflux": True},
        },
    ]

    posterior = update_posterior_from_meal_logs(prior, logs)

    lactase = posterior["enzyme_levels"]["lactase_Vmax"]
    aldh = posterior["enzyme_levels"]["ALDH_Vmax"]
    reflux_threshold = posterior["symptom_thresholds"]["reflux_pressure_threshold"]
    pain_threshold = posterior["symptom_thresholds"]["pain_irritation_threshold"]

    assert lactase["mean"] < 0.8
    assert lactase["variance"] < 0.2
    assert aldh["mean"] < 1.0
    assert aldh["variance"] < 0.3
    assert reflux_threshold["mean"] < 0.75
    assert reflux_threshold["variance"] < 0.12
    assert pain_threshold["mean"] < 0.65
    assert pain_threshold["variance"] < 0.10


def test_profile_builder_overlays_generalized_posterior_means():
    from gastric_engine.physiology.profile_builder import build_profile

    profile = build_profile(
        {},
        learned_physiology={
            "enzyme_levels": {
                "ALDH_Vmax": {"mean": 0.42, "variance": 0.05},
            },
            "symptom_thresholds": {
                "reflux_pressure_threshold": {"mean": 0.61, "variance": 0.04},
            },
        },
    )

    assert profile["enzyme_levels"]["ALDH_Vmax"] == 0.42
    assert profile["symptom_thresholds"]["reflux_pressure_threshold"] == 0.61


def _peak_observations(result):
    return {
        symptom: max(values)
        for symptom, values in result["symptom_curves"].items()
        if symptom != "time_min"
    }


def test_calibration_fit_noops_to_seed_defaults_below_minimum_samples():
    from gastric_engine.learning.calibration_fit import (
        DEFAULT_CALIBRATION_PARAMETERS,
        fit_calibration_constants,
    )

    result = fit_calibration_constants(
        [
            {
                "chemicals": {"CO2_dissolved": 2.0, "caffeine": 40},
                "meal_physical": {"solid_volume_ml": 200, "liquid_volume_ml": 400},
                "clinical_profile": {"reflux_gord": True},
                "simulation_config": {"duration_min": 60, "output_dt_min": 20},
                "observed_peaks": {"reflux": 0.5},
            }
        ],
        min_samples=3,
    )

    assert result.used_defaults is True
    assert result.parameters == DEFAULT_CALIBRATION_PARAMETERS
    assert result.fitted_error == result.seed_error


def test_calibration_fit_reduces_synthetic_curve_error_and_stays_clamped():
    from gastric_engine.core.engine import simulate_core
    from gastric_engine.learning.calibration_fit import (
        PARAMETER_RANGES,
        fit_calibration_constants,
    )
    from gastric_engine.physiology.profile_builder import build_profile

    requests = [
        {
            "chemicals": {"CO2_dissolved": 2.0, "caffeine": 60},
            "meal_physical": {"solid_volume_ml": 350, "liquid_volume_ml": 550},
            "clinical_profile": {"reflux_gord": True},
            "simulation_config": {"duration_min": 80, "output_dt_min": 20},
        },
        {
            "chemicals": {"lactose": 18, "FODMAP": 3},
            "meal_physical": {"solid_volume_ml": 150, "liquid_volume_ml": 450},
            "clinical_profile": {"lactose_intolerance": True},
            "simulation_config": {"duration_min": 180, "output_dt_min": 30},
        },
        {
            "chemicals": {"fat": 45, "CO2_dissolved": 1.2},
            "meal_physical": {"solid_volume_ml": 500, "liquid_volume_ml": 450},
            "clinical_profile": {},
            "simulation_config": {"duration_min": 120, "output_dt_min": 30},
        },
    ]
    target_parameters = {
        "symptom_gain": 6.5,
        "co2_gas_ml_per_g": 520.0,
        "fermentation_gas_ml_per_g": 150.0,
        "bloating_osmotic_weight": 0.55,
        "material_drop": 1.0,
    }

    logs = []
    for request in requests:
        result = simulate_core(
            request["chemicals"],
            request["meal_physical"],
            build_profile(request["clinical_profile"]),
            {**request["simulation_config"], "calibration": target_parameters},
        )
        logs.append({**request, "observed_peaks": _peak_observations(result)})

    fit = fit_calibration_constants(logs, min_samples=3)

    assert fit.used_defaults is False
    assert fit.fitted_error < fit.seed_error
    for name, value in fit.parameters.items():
        minimum, maximum = PARAMETER_RANGES[name]
        assert minimum <= value <= maximum


def test_calibration_fit_passes_candidate_parameters_without_mutating_globals(monkeypatch):
    from gastric_engine.core import counterfactual
    from gastric_engine.learning import calibration_fit
    from gastric_engine.utils import calibration

    seed_gain = calibration.SYMPTOM_GAIN
    seed_gas = calibration.CO2_GAS_ML_PER_G
    seed_material = counterfactual.MATERIAL_DROP
    seen_configs = []

    def fake_simulate_core(chemicals, meal_physical, physiology, config):
        assert calibration.SYMPTOM_GAIN == seed_gain
        assert calibration.CO2_GAS_ML_PER_G == seed_gas
        assert counterfactual.MATERIAL_DROP == seed_material
        seen_configs.append(config)
        gain = config["calibration"]["symptom_gain"]
        return {"symptom_curves": {"time_min": [0.0], "reflux": [gain / 20.0]}}

    monkeypatch.setattr(calibration_fit, "simulate_core", fake_simulate_core)

    fit = calibration_fit.fit_calibration_constants(
        [
            {
                "chemicals": {"CO2_dissolved": 2.0},
                "meal_physical": {"solid_volume_ml": 100, "liquid_volume_ml": 300},
                "clinical_profile": {},
                "simulation_config": {"duration_min": 10, "output_dt_min": 10},
                "observed_peaks": {"reflux": 0.2},
            },
            {
                "chemicals": {"CO2_dissolved": 1.6},
                "meal_physical": {"solid_volume_ml": 100, "liquid_volume_ml": 300},
                "clinical_profile": {},
                "simulation_config": {"duration_min": 10, "output_dt_min": 10},
                "observed_peaks": {"reflux": 0.3},
            },
            {
                "chemicals": {"CO2_dissolved": 1.2},
                "meal_physical": {"solid_volume_ml": 100, "liquid_volume_ml": 300},
                "clinical_profile": {},
                "simulation_config": {"duration_min": 10, "output_dt_min": 10},
                "observed_peaks": {"reflux": 0.4},
            },
        ],
        min_samples=3,
    )

    assert fit.used_defaults is False
    assert seen_configs
    assert all("calibration" in config for config in seen_configs)
    assert calibration.SYMPTOM_GAIN == seed_gain
    assert calibration.CO2_GAS_ML_PER_G == seed_gas
    assert counterfactual.MATERIAL_DROP == seed_material
