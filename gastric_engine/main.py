"""ASGI entrypoint for production deployments."""

import os
from pathlib import Path


def _load_dotenv() -> None:
    """Load the repo-root .env into os.environ (no dependency, no overrides).

    The Gemini client reads GEMINI_API_KEY / GEMINI_MODEL straight from the
    environment, so ``uvicorn gastric_engine.main:app`` needs them present.
    Variables already set in the real environment always take precedence.
    """
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

from gastric_engine.api.routes import app  # noqa: E402  (env must load first)

__all__ = ["app"]
