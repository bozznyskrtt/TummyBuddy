"""Fit calibration constants from meal outcome logs."""

from __future__ import annotations

from dataclasses import dataclass

from scipy.optimize import minimize

from gastric_engine.core.engine import simulate_core
from gastric_engine.physiology.profile_builder import build_profile
from gastric_engine.utils import calibration


DEFAULT_CALIBRATION_PARAMETERS = calibration.runtime_parameters()

PARAMETER_RANGES = {
    "symptom_gain": (2.0, 20.0),
    "co2_gas_ml_per_g": (200.0, 700.0),
    "fermentation_gas_ml_per_g": (60.0, 240.0),
    "bloating_osmotic_weight": (0.0, 1.0),
    "material_drop": (0.1, 10.0),
}


@dataclass(frozen=True)
class CalibrationFitResult:
    parameters: dict[str, float]
    seed_error: float
    fitted_error: float
    used_defaults: bool
    sample_count: int


def fit_calibration_constants(
    logs: list[dict],
    *,
    min_samples: int = 5,
) -> CalibrationFitResult:
    logs = list(logs or [])
    seed_parameters = dict(DEFAULT_CALIBRATION_PARAMETERS)
    seed_error = _prediction_error(logs, seed_parameters)
    if len(logs) < min_samples:
        return CalibrationFitResult(
            parameters=seed_parameters,
            seed_error=seed_error,
            fitted_error=seed_error,
            used_defaults=True,
            sample_count=len(logs),
        )

    names = list(seed_parameters)
    result = minimize(
        lambda values: _prediction_error(logs, _from_unit_vector(names, values)),
        _to_unit_vector(seed_parameters, names),
        bounds=[(0.0, 1.0)] * len(names),
        method="L-BFGS-B",
        options={"maxiter": 40},
    )
    fitted_parameters = _from_unit_vector(names, result.x)
    fitted_error = _prediction_error(logs, fitted_parameters)

    if fitted_error > seed_error:
        fitted_parameters = seed_parameters
        fitted_error = seed_error

    return CalibrationFitResult(
        parameters=fitted_parameters,
        seed_error=seed_error,
        fitted_error=fitted_error,
        used_defaults=False,
        sample_count=len(logs),
    )


def _prediction_error(logs: list[dict], parameters: dict[str, float]) -> float:
    if not logs:
        return 0.0
    total = 0.0
    comparisons = 0
    for log in logs:
        observed = log.get("observed_peaks", {}) or {}
        if not observed:
            continue
        simulation_config = {
            **(log.get("simulation_config") or {}),
            "calibration": parameters,
        }
        result = simulate_core(
            log.get("chemicals", {}) or {},
            log.get("meal_physical", {}) or {},
            build_profile(
                log.get("clinical_profile", {}) or {},
                learned_physiology=log.get("learned_physiology"),
            ),
            simulation_config,
        )
        for symptom, observed_peak in observed.items():
            if symptom not in result["symptom_curves"]:
                continue
            predicted = max(result["symptom_curves"][symptom])
            total += (predicted - float(observed_peak)) ** 2
            comparisons += 1
    return total / max(comparisons, 1)


def _to_unit_vector(parameters: dict[str, float], names: list[str]) -> list[float]:
    values = []
    for name in names:
        minimum, maximum = PARAMETER_RANGES[name]
        values.append((parameters[name] - minimum) / (maximum - minimum))
    return values


def _from_unit_vector(names: list[str], values) -> dict[str, float]:
    parameters = {}
    for name, value in zip(names, values):
        minimum, maximum = PARAMETER_RANGES[name]
        parameters[name] = _clamp(name, minimum + float(value) * (maximum - minimum))
    return parameters


def _clamp(name: str, value: float) -> float:
    minimum, maximum = PARAMETER_RANGES[name]
    return min(max(float(value), minimum), maximum)
