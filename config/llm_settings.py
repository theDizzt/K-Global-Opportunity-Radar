"""OpenAI 보고서 생성에 필요한 설정만 안전하게 읽는다."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from config.settings import ROOT_DIR


OPENAI_ENV_KEYS = {
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_REPORTS_ENABLED",
    "OPENAI_API_TIMEOUT",
}


@dataclass(frozen=True)
class OpenAISettings:
    enabled: bool
    api_key: str = field(repr=False)
    model: str
    timeout_seconds: float

    @property
    def is_configured(self):
        return self.enabled and bool(self.api_key)


def load_openai_settings(env_path: str | Path | None = None):
    """프로세스 환경을 우선하고 .env에서는 OpenAI 관련 항목만 읽는다."""
    file_values = _read_allowed_env(Path(env_path) if env_path else ROOT_DIR / ".env")

    def get_value(name: str, default: str = ""):
        return os.getenv(name, file_values.get(name, default)).strip()

    api_key = get_value("OPENAI_API_KEY")
    enabled_value = get_value(
        "OPENAI_REPORTS_ENABLED",
        "true" if api_key else "false",
    )
    timeout_value = get_value("OPENAI_API_TIMEOUT", "45")
    try:
        timeout_seconds = float(timeout_value)
    except ValueError as exc:
        raise ValueError("OPENAI_API_TIMEOUT must be a number") from exc
    if timeout_seconds <= 0:
        raise ValueError("OPENAI_API_TIMEOUT must be greater than zero")

    return OpenAISettings(
        enabled=enabled_value.lower() in {"1", "true", "yes", "on"},
        api_key=api_key,
        model=get_value("OPENAI_MODEL", "gpt-5.6-sol"),
        timeout_seconds=timeout_seconds,
    )


def _read_allowed_env(path: Path):
    if not path.is_file():
        return {}

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(),
        1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid .env line {line_number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in OPENAI_ENV_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'\"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values
