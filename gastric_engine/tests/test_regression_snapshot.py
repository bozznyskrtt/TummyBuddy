import json
from pathlib import Path

import pytest


SNAPSHOT_PATH = Path(__file__).with_name("fixtures") / "regression_snapshot.json"


def test_regression_snapshot_curves_match_frozen_baseline():
    from gastric_engine.core.engine import simulate_core
    from gastric_engine.physiology.profile_builder import build_profile

    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    scenarios = {
        "coke_reflux": {
            "chemicals": {"CO2_dissolved": 2.1, "caffeine": 60, "fat": 35},
            "meal_physical": {"solid_volume_ml": 450, "liquid_volume_ml": 650},
            "physiology": build_profile({"reflux_gord": True}),
            "config": {"duration_min": 120, "output_dt_min": 10},
        },
        "durian_beer": {
            "chemicals": {"ethanol": 18, "durian_sulfur": 1},
            "meal_physical": {"solid_volume_ml": 100, "liquid_volume_ml": 300},
            "physiology": build_profile({}),
            "config": {"duration_min": 90, "output_dt_min": 10},
        },
        "milkshake": {
            "chemicals": {"lactose": 18, "fat": 25, "FODMAP": 2},
            "meal_physical": {"solid_volume_ml": 250, "liquid_volume_ml": 450},
            "physiology": build_profile({"lactose_intolerance": True}),
            "config": {"duration_min": 360, "output_dt_min": 30},
        },
    }

    actual = {}
    for name, request in scenarios.items():
        result = simulate_core(**request)
        actual[name] = {
            "symptom_curves": result["symptom_curves"],
            "mechanism_curves": result["mechanism_curves"],
        }

    assert actual.keys() == expected.keys()
    for scenario, expected_curves in expected.items():
        assert actual[scenario].keys() == expected_curves.keys()
        for curve_group, curves in expected_curves.items():
            assert actual[scenario][curve_group].keys() == curves.keys()
            for curve_name, expected_values in curves.items():
                assert actual[scenario][curve_group][curve_name] == pytest.approx(
                    expected_values,
                    abs=1e-6,
                    rel=0.0,
                )
