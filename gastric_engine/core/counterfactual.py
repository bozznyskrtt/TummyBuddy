"""Counterfactual symptom attribution."""

from __future__ import annotations

from gastric_engine.utils.kinetics import curve_auc, peak_time


# Minimum AUC drop (symptom-probability * minutes) to count as a real driver.
MATERIAL_DROP = 1.0

MECHANISMS = {
    "CO2_dissolved": "carbonation outgassing raised fundus pressure",
    "fat": "delayed emptying kept the stomach full and pressurized",
    "caffeine": "LES relaxation and acid stimulation",
    "ethanol": "LES relaxation and mucosal irritation",
    "lactose": "undigested lactose raised osmotic load and fermentation",
    "FODMAP": "fermentable carbohydrates increased intestinal gas",
    "acid_load": "meal acidity increased mucosal irritation",
    "spice_capsaicin": "capsaicin irritated the mucosa",
    "durian_sulfur": "ALDH inhibition increased acetaldehyde irritation",
}


def counterfactual_attribution(
    chemicals: dict[str, float],
    meal_physical: dict[str, float],
    physiology: dict,
    kb,
    config: dict,
    baseline: dict,
    simulate_core_fn,
) -> dict:
    time = baseline["symptom_curves"]["time_min"]
    # Attribute on AUC (total symptom burden over time), not peak: when a peak
    # saturates near 1.0 the peak barely moves, but the AUC still discriminates.
    base_aucs = {
        symptom: curve_auc(time, values)
        for symptom, values in baseline["symptom_curves"].items()
        if symptom != "time_min"
    }
    raw: dict[str, list[dict]] = {}

    for chemical, amount in chemicals.items():
        if amount <= 0:
            continue
        reduced = dict(chemicals)
        reduced.pop(chemical, None)
        alternative = simulate_core_fn(
            reduced,
            meal_physical,
            physiology,
            config,
            kb=kb,
        )
        for symptom, base_auc in base_aucs.items():
            alt_auc = curve_auc(time, alternative["symptom_curves"].get(symptom, []))
            drop = base_auc - alt_auc
            if drop > MATERIAL_DROP:
                raw.setdefault(symptom, []).append(
                    {
                        "chemical": chemical,
                        "drop": drop,
                        "mechanism": MECHANISMS.get(
                            chemical, "this compound changed the simulated state"
                        ),
                    }
                )

    attributed = {}
    for symptom, drivers in raw.items():
        total = sum(driver["drop"] for driver in drivers)
        if total <= 0:
            continue
        ranked = sorted(drivers, key=lambda driver: driver["drop"], reverse=True)
        attributed[symptom] = {
            "peak_time_min": peak_time(time, baseline["symptom_curves"].get(symptom, [])),
            "drivers": [
                {
                    "chemical": driver["chemical"],
                    "contribution": driver["drop"] / total,
                    "mechanism": driver["mechanism"],
                }
                for driver in ranked
            ],
            "advice": _advice(symptom, ranked[0], base_aucs[symptom]),
        }
    return attributed


def _advice(symptom: str, top_driver: dict, base_auc: float) -> str:
    percent = round(top_driver["drop"] / max(base_auc, 1e-6) * 100)
    return (
        f"Skipping {top_driver['chemical']} would lower peak {symptom} "
        f"by about {percent}% in this simulation."
    )
