"""Bayesian-style updates for learned physiology parameters."""

from __future__ import annotations

from copy import deepcopy


DEFAULT_PRIORS = {
    "enzyme_levels": {
        "lactase_Vmax": {"mean": 1.0, "variance": 0.3},
        "amylase_Vmax": {"mean": 1.0, "variance": 0.3},
        "pepsin_Vmax": {"mean": 1.0, "variance": 0.3},
        "ADH_Vmax": {"mean": 1.0, "variance": 0.3},
        "ALDH_Vmax": {"mean": 1.0, "variance": 0.3},
    },
    "symptom_thresholds": {
        "reflux_pressure_threshold": {"mean": 0.75, "variance": 0.12},
        "bloating_volume_threshold": {"mean": 0.80, "variance": 0.12},
        "pain_irritation_threshold": {"mean": 0.65, "variance": 0.10},
        "diarrhea_osmotic_threshold": {"mean": 1.15, "variance": 0.10},
    },
}


def _bayesian_update(mean: float, variance: float, evidence: float, evidence_var: float) -> dict:
    precision = 1.0 / max(variance, 1e-6)
    evidence_precision = 1.0 / max(evidence_var, 1e-6)
    updated_var = 1.0 / (precision + evidence_precision)
    updated_mean = updated_var * (mean * precision + evidence * evidence_precision)
    return {"mean": updated_mean, "variance": updated_var}


def update_posterior_from_meal_logs(prior: dict, logs: list[dict]) -> dict:
    posterior = _initial_posterior(prior)

    for log in logs:
        for section, key, evidence, evidence_var in _evidence_from_log(log):
            current = posterior.setdefault(section, {}).setdefault(
                key,
                {"mean": evidence, "variance": 0.3},
            )
            current.update(
                _bayesian_update(
                    float(current.get("mean", evidence)),
                    float(current.get("variance", 0.3)),
                    evidence,
                    evidence_var,
                )
            )

    return posterior


def _initial_posterior(prior: dict) -> dict:
    posterior = deepcopy(DEFAULT_PRIORS)
    for section, values in (prior or {}).items():
        if not isinstance(values, dict):
            continue
        section_target = posterior.setdefault(section, {})
        for key, distribution in values.items():
            section_target[key] = dict(distribution)
    return posterior


def _evidence_from_log(log: dict) -> list[tuple[str, str, float, float]]:
    chemicals = log.get("chemicals", {}) or {}
    symptoms = log.get("symptoms_reported", {}) or {}
    evidence: list[tuple[str, str, float, float]] = []

    lactose = _amount(chemicals, "lactose")
    fodmap = _amount(chemicals, "FODMAP")
    ethanol = _amount(chemicals, "ethanol")
    co2 = _amount(chemicals, "CO2_dissolved")
    caffeine = _amount(chemicals, "caffeine")
    acid = _amount(chemicals, "acid_load")
    spice = _amount(chemicals, "spice_capsaicin")
    fat = _amount(chemicals, "fat")
    starch = _amount(chemicals, "starch")

    if lactose > 5.0:
        evidence.append(
            (
                "enzyme_levels",
                "lactase_Vmax",
                0.15 if _reported(symptoms, "diarrhea") else 1.0,
                0.04,
            )
        )
        evidence.append(
            (
                "symptom_thresholds",
                "diarrhea_osmotic_threshold",
                0.55 if _reported(symptoms, "diarrhea") else 0.75,
                0.04,
            )
        )

    if ethanol > 8.0:
        evidence.append(
            (
                "enzyme_levels",
                "ALDH_Vmax",
                0.35 if _reported(symptoms, "upper_pain") else 1.0,
                0.08,
            )
        )
        evidence.append(
            (
                "symptom_thresholds",
                "pain_irritation_threshold",
                0.55 if _reported(symptoms, "upper_pain") else 0.70,
                0.04,
            )
        )

    if co2 > 0.5 or caffeine > 20.0 or ethanol > 8.0:
        evidence.append(
            (
                "symptom_thresholds",
                "reflux_pressure_threshold",
                0.62 if _reported(symptoms, "reflux") else 0.80,
                0.04,
            )
        )

    if acid > 0.2 or spice > 0.05:
        evidence.append(
            (
                "symptom_thresholds",
                "pain_irritation_threshold",
                0.55 if _reported(symptoms, "upper_pain") else 0.72,
                0.04,
            )
        )

    if fodmap > 1.0:
        evidence.append(
            (
                "symptom_thresholds",
                "diarrhea_osmotic_threshold",
                0.55 if _reported(symptoms, "diarrhea") else 0.75,
                0.04,
            )
        )
        evidence.append(
            (
                "symptom_thresholds",
                "bloating_volume_threshold",
                0.62 if _reported(symptoms, "bloating") else 0.85,
                0.05,
            )
        )

    if starch > 30.0:
        evidence.append(
            (
                "enzyme_levels",
                "amylase_Vmax",
                0.55 if _reported(symptoms, "bloating") else 1.0,
                0.10,
            )
        )

    if fat > 20.0 or co2 > 0.5:
        evidence.append(
            (
                "symptom_thresholds",
                "bloating_volume_threshold",
                0.62 if _reported(symptoms, "bloating") else 0.85,
                0.05,
            )
        )

    return evidence


def _amount(chemicals: dict, key: str) -> float:
    return float(chemicals.get(key, 0.0) or 0.0)


def _reported(symptoms: dict, key: str) -> bool:
    return bool(symptoms.get(key) or symptoms.get("pain" if key == "upper_pain" else key))
