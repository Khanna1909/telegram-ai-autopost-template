from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    pass


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    required = ("brand", "generation", "telegram", "safety", "content")
    missing = [key for key in required if key not in data]
    if missing:
        raise ConfigError(f"Missing config sections: {', '.join(missing)}")
    return data


def env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def live_mode(config: dict[str, Any]) -> bool:
    dry_run = env_flag("DRY_RUN", bool(config["safety"].get("dry_run", True)))
    telegram_enabled = env_flag(
        "TELEGRAM_ENABLED", bool(config["telegram"].get("enabled", False))
    )
    explicit_live = env_flag("ALLOW_LIVE_PUBLISH", False)
    if config["safety"].get("require_explicit_live_flag", True):
        return not dry_run and telegram_enabled and explicit_live
    return not dry_run and telegram_enabled


def require_secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"Required secret {name} is empty")
    return value

