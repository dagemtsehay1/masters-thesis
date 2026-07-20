"""Loads and validates the application configuration.

Resolution order (later steps override earlier ones):
    config/presets/default.yaml
    -> config/presets/<preset>.yaml   (if --preset was given)
    -> an explicit --config file      (if given)
    -> environment variables          (machine-specific values only)

The result is validated as a single `AppConfig`; any problem is raised as
one aggregated `ConfigError` so startup fails with a clear message instead
of running with a partially-invalid configuration.
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import ValidationError

from src.config.schema import AppConfig

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PRESETS_DIR = REPO_ROOT / "config" / "presets"
DEFAULT_CONFIG_PATH = PRESETS_DIR / "default.yaml"

# Only machine-specific values get environment overrides - everything else
# belongs in a YAML preset so experiments stay reproducible.
_ENV_OVERRIDES = {
    "APP_CAMERA_DEVICE": ("camera", "device_index", int),
    "APP_MIC_DEVICE": ("microphone", "device_index", int),
    "APP_COPPELIA_HOST": ("coppelia", "host", str),
    "APP_COPPELIA_PORT": ("coppelia", "port", int),
}


class ConfigError(Exception):
    """Raised when configuration files are missing, malformed, or invalid."""


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Could not parse YAML file {path}: {exc}") from exc
    return data or {}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _apply_env_overrides(data: Dict[str, Any]) -> Dict[str, Any]:
    for env_name, (section, field, cast) in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_name)
        if raw is None:
            continue
        try:
            value = cast(raw)
        except ValueError as exc:
            raise ConfigError(f"Environment variable {env_name}={raw!r} is not a valid {cast.__name__}") from exc
        data.setdefault(section, {})
        data[section][field] = value
    return data


def _format_validation_error(exc: ValidationError) -> str:
    lines = [f"Configuration is invalid ({len(exc.errors())} problem(s)):"]
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        lines.append(f"  - {location}: {error['msg']}")
    return "\n".join(lines)


def load_config(preset: Optional[str] = None, config_path: Optional[str] = None) -> AppConfig:
    merged = _load_yaml(DEFAULT_CONFIG_PATH)

    if preset:
        preset_file = PRESETS_DIR / f"{preset}.yaml"
        merged = _deep_merge(merged, _load_yaml(preset_file))

    if config_path:
        merged = _deep_merge(merged, _load_yaml(Path(config_path)))

    merged = _apply_env_overrides(merged)

    try:
        config = AppConfig(**merged)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(exc)) from exc

    if preset:
        config.general.active_preset = preset
    return config
