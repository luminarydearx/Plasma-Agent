from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_CONFIG_FILE = Path.home() / ".plasma" / "config.json"


def _load_config() -> dict[str, Any]:
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_config(data: dict[str, Any]) -> None:
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_default_model() -> str | None:
    config = _load_config()
    return config.get("default_model")


def set_default_model(model: str) -> None:
    config = _load_config()
    config["default_model"] = model
    _save_config(config)


def get_config_value(key: str, default: Any = None) -> Any:
    config = _load_config()
    return config.get(key, default)


def set_config_value(key: str, value: Any) -> None:
    config = _load_config()
    config[key] = value
    _save_config(config)


def get_full_config() -> dict[str, Any]:
    return _load_config()
