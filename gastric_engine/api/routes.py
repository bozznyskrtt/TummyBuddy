"""FastAPI routes plus plain-call handlers for tests and local use."""

from __future__ import annotations

from gastric_engine.core.engine import simulate
from gastric_engine.knowledge_base.loader import load_knowledge_base
from gastric_engine.physiology.profile_builder import build_profile
from gastric_engine.safety.red_flags import safety_flags

try:  # pragma: no cover - FastAPI is not installed in the local runner
    from fastapi import FastAPI
except Exception:  # pragma: no cover
    FastAPI = None


app = FastAPI(title="TummyBuddy Gastric Engine") if FastAPI else None


def health() -> dict[str, str]:
    return {"status": "ok"}


def simulate_endpoint(payload: dict) -> dict:
    kb = load_knowledge_base()
    chemicals = payload.get("chemicals", {}) or {}
    unknown = sorted(
        key
        for key, value in chemicals.items()
        if key not in kb.compound_keys and isinstance(value, (int, float)) and value
    )
    known_chemicals = {
        key: value
        for key, value in chemicals.items()
        if key in kb.compound_keys and isinstance(value, (int, float))
    }
    flags = safety_flags(payload.get("symptoms_reported"))
    physiology = build_profile(
        payload.get("clinical_profile", {}),
        learned_physiology=payload.get("learned_physiology"),
    )
    result = simulate(
        known_chemicals,
        payload.get("meal_physical", {}),
        physiology,
        payload.get("simulation_config"),
        kb=kb,
    )
    result["unknown_compounds"] = unknown
    result["safety_flags"] = flags
    if unknown or flags:
        result["summary"]["confidence"] = "low"
    return result


if app is not None:  # pragma: no cover

    @app.get("/health")
    def _health_route():
        return health()

    @app.post("/simulate")
    def _simulate_route(payload: dict):
        return simulate_endpoint(payload)
