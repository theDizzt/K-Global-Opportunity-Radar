from __future__ import annotations

import os
from pathlib import Path


def load_env(path: str | Path = ".env", *, override: bool = False) -> dict[str, str]:
    """Load a simple KEY=VALUE file without adding a runtime dependency."""
    env_path = Path(path)
    loaded: dict[str, str] = {}
    if not env_path.exists():
        return loaded

    for line_number, raw_line in enumerate(env_path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid .env line {line_number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if not key:
            raise ValueError(f"Invalid .env line {line_number}: empty key")
        loaded[key] = value
        if override or key not in os.environ:
            os.environ[key] = value
    return loaded


def require_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required setting {name} is empty. Add it to .env.")
    return value
