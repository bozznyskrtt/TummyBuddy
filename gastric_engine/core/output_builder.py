"""Build public response dictionaries from simulated history."""

from __future__ import annotations

from gastric_engine.utils.kinetics import curve_peak, peak_time


MECHANISM_KEYS = [
    "time_min",
    "volume_ml",
    "solid_volume_ml",
    "liquid_volume_ml",
    "gas_volume_ml",
    "gastric_pressure",
    "fundus_pressure",
    "pH",
    "osmolality",
    "lactose_remaining_g",
    "intestine_gas_ml",
    "intestine_osmolality",
    "acetaldehyde_g",
    "cramping",
    "irritation",
]


def mechanism_curves(history: list[dict]) -> dict[str, list[float]]:
    return {key: [point.get(key, 0.0) for point in history] for key in MECHANISM_KEYS}


def build_summary(symptom_curves: dict[str, list[float]], confidence: str = "medium") -> dict:
    time = symptom_curves.get("time_min", [])
    peaks = {
        symptom: curve_peak(values)
        for symptom, values in symptom_curves.items()
        if symptom != "time_min"
    }
    main_symptom = max(peaks, key=peaks.get) if peaks else "none"
    main_peak = peaks.get(main_symptom, 0.0)
    if main_peak < 0.2:
        main_symptom = "none"
    if main_peak >= 0.7:
        risk = "high"
    elif main_peak >= 0.4:
        risk = "medium"
    elif main_peak >= 0.2:
        risk = "low"
    else:
        risk = "low"

    return {
        "main_symptom": main_symptom,
        "risk_level": risk,
        "peak_time_min": peak_time(time, symptom_curves.get(main_symptom, []))
        if main_symptom != "none"
        else 0,
        "confidence": confidence,
    }


def build_output(
    history: list[dict],
    symptom_curves: dict[str, list[float]],
    *,
    root_causes: dict | None = None,
    unknown_compounds: list[str] | None = None,
    safety_flags: list[dict] | None = None,
    metadata: dict | None = None,
    confidence: str = "medium",
) -> dict:
    return {
        "summary": build_summary(symptom_curves, confidence=confidence),
        "symptom_curves": symptom_curves,
        "mechanism_curves": mechanism_curves(history),
        "root_causes": root_causes or {},
        "unknown_compounds": unknown_compounds or [],
        "safety_flags": safety_flags or [],
        "metadata": metadata or {},
    }
