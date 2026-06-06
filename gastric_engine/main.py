"""ASGI entrypoint for production deployments."""

from gastric_engine.api.routes import app

__all__ = ["app"]
