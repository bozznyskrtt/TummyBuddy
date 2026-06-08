"""Persistent cache for one-time substance characterization."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any


DEFAULT_CACHE_PATH = Path("/tmp/gastric_engine_characterization_cache.json")


class CharacterizationCache:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else default_cache_path()
        self.entries = self._read()

    def get(self, substance: str) -> dict[str, Any] | None:
        entry = self.entries.get(_cache_key(substance))
        return deepcopy(entry) if entry is not None else None

    def set(self, result) -> None:
        self.entries[_cache_key(result.substance)] = asdict(result)
        self._write()

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(self.entries, handle, indent=2, sort_keys=True)
            handle.write("\n")


def default_cache_path() -> Path:
    return Path(os.environ.get("GASTRIC_ENGINE_CHARACTERIZATION_CACHE", DEFAULT_CACHE_PATH))


def _cache_key(substance: str) -> str:
    return substance.strip().lower()
