"""Bayesian-style updates for learned physiology parameters."""

from __future__ import annotations


def _bayesian_update(mean: float, variance: float, evidence: float, evidence_var: float) -> dict:
    precision = 1.0 / max(variance, 1e-6)
    evidence_precision = 1.0 / max(evidence_var, 1e-6)
    updated_var = 1.0 / (precision + evidence_precision)
    updated_mean = updated_var * (mean * precision + evidence * evidence_precision)
    return {"mean": updated_mean, "variance": updated_var}


def update_posterior_from_meal_logs(prior: dict, logs: list[dict]) -> dict:
    posterior = {
        "enzyme_levels": {
            "lactase_Vmax": dict(
                prior.get("enzyme_levels", {})
                .get("lactase_Vmax", {"mean": 1.0, "variance": 0.3})
            )
        }
    }
    lactase = posterior["enzyme_levels"]["lactase_Vmax"]

    for log in logs:
        lactose = float(log.get("chemicals", {}).get("lactose", 0.0) or 0.0)
        diarrhea = bool(log.get("symptoms_reported", {}).get("diarrhea"))
        if lactose <= 5.0:
            continue
        evidence = 0.15 if diarrhea else 1.0
        updated = _bayesian_update(
            float(lactase.get("mean", 1.0)),
            float(lactase.get("variance", 0.3)),
            evidence,
            0.04,
        )
        lactase.update(updated)

    return posterior
