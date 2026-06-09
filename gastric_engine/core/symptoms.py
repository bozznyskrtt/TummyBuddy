"""Symptom curves derived from emergent state thresholds."""

from __future__ import annotations

from gastric_engine.utils.kinetics import sigmoid


def derive_symptoms(
    history: list[dict],
    physiology: dict,
    calibration_params: dict,
) -> dict[str, list[float]]:
    thresholds = physiology.get("symptom_thresholds", {})
    capacity = float(physiology.get("physiology", {}).get("gastric_capacity_ml", 1000.0))
    reflux_threshold = float(thresholds.get("reflux_pressure_threshold", 0.75))
    bloating_threshold = float(thresholds.get("bloating_volume_threshold", 0.80))
    diarrhea_threshold = float(thresholds.get("diarrhea_osmotic_threshold", 0.70))
    pain_threshold = float(thresholds.get("pain_irritation_threshold", 0.65))

    time = [point["time_min"] for point in history]
    symptom_gain = calibration_params["symptom_gain"]
    reflux = [
        sigmoid((point["fundus_pressure"] - reflux_threshold) * symptom_gain)
        for point in history
    ]
    # Bloating is gas distension (gastric CO2 outgassing + intestinal
    # fermentation) plus osmotic water influx -- all of which BUILD over time.
    # Raw meal volume at t=0 is fullness, not bloating, so it is not used here.
    bloating = [
        sigmoid(
            (
                (point["gas_volume_ml"] + point.get("intestine_gas_ml", 0.0)) / capacity
                + calibration_params["bloating_osmotic_weight"]
                * max(0.0, point["osmolality"] - 0.5)
                - bloating_threshold
            )
            * symptom_gain
        )
        for point in history
    ]
    # Gains lowered (was 8.0) so osmotic/irritant load ramps these symptoms
    # gradually rather than saturating to ~100% once the threshold is crossed.
    diarrhea = [
        sigmoid((point["intestine_osmolality"] - diarrhea_threshold) * 2.2)
        for point in history
    ]
    upper_pain = [
        sigmoid((point["irritation"] - pain_threshold) * 4.0) for point in history
    ]

    return {
        "time_min": time,
        "reflux": reflux,
        "bloating": bloating,
        "diarrhea": diarrhea,
        "upper_pain": upper_pain,
    }
