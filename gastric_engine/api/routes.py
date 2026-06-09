"""FastAPI routes plus plain-call handlers for tests and local use."""

from __future__ import annotations

import os
from pathlib import Path

from gastric_engine.characterization.providers import build_agent_provider
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


def _characterization_wiring():
    if os.environ.get("GASTRIC_ENGINE_CHARACTERIZER_MODE") != "agent":
        return None, False
    provider = build_agent_provider()
    return provider, provider is not None


def simulate_endpoint(payload: dict) -> dict:
    kb = load_knowledge_base()
    chemicals = payload.get("chemicals", {}) or {}
    clean_chemicals = {
        key: value
        for key, value in chemicals.items()
        if isinstance(value, (int, float)) and float(value) > 0
    }
    flags = safety_flags(payload.get("symptoms_reported"))
    physiology = build_profile(
        payload.get("clinical_profile", {}),
        learned_physiology=payload.get("learned_physiology"),
    )
    agent, agent_enabled = _characterization_wiring()
    result = simulate(
        clean_chemicals,
        payload.get("meal_physical", {}),
        physiology,
        payload.get("simulation_config"),
        kb=kb,
        characterization_agent=agent,
        characterization_agent_enabled=agent_enabled,
    )
    result["unknown_compounds"] = []
    result["safety_flags"] = flags
    if flags:
        result["summary"]["confidence"] = "low"
    return result


def _lazy_analyze_meal(image: object, **kwargs: object) -> dict:
    """Lazy proxy so the orchestrator import is deferred (breaks circular import)."""
    from gastric_engine.pipeline.orchestrator import analyze_meal as _analyze_meal  # noqa: PLC0415

    return _analyze_meal(image, **kwargs)


# Module-level name so tests can monkeypatch ``routes.analyze_meal``.
analyze_meal = _lazy_analyze_meal


def analyze_image_endpoint(
    image_bytes: bytes,
    *,
    clinical_profile: dict | None = None,
    simulation_config: dict | None = None,
) -> dict:
    return analyze_meal(
        image_bytes,
        clinical_profile=clinical_profile or {},
        simulation_config=simulation_config,
    )


STATIC_DIR = Path(__file__).resolve().parent / "static"


if app is not None:  # pragma: no cover
    import json as _json

    from fastapi import Form, UploadFile
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/health")
    def _health_route():
        return health()

    @app.post("/simulate")
    def _simulate_route(payload: dict):
        return simulate_endpoint(payload)

    @app.get("/")
    def _index_route():
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.post("/analyze-image")
    async def _analyze_image_route(
        image: UploadFile,
        clinical_profile: str = Form("{}"),
        simulation_config: str = Form("null"),
    ):
        return analyze_image_endpoint(
            await image.read(),
            clinical_profile=_json.loads(clinical_profile),
            simulation_config=_json.loads(simulation_config),
        )
