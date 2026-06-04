# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""CLI configuration — reads/writes ~/.config/quickcall/config.json"""

import json
import os
from pathlib import Path


_CONFIG_DIR = Path.home() / ".config" / "quickcall"
_CONFIG_PATH = _CONFIG_DIR / "config.json"


def _ensure_dir() -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, str]:
    """Load saved CLI config. Returns empty dict if none exists."""
    if not _CONFIG_PATH.exists():
        return {}
    try:
        with open(_CONFIG_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(**kwargs: str) -> None:
    """Save CLI config key/value pairs."""
    _ensure_dir()
    cfg = load_config()
    cfg.update(kwargs)
    with open(_CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def get_api_url() -> str:
    """Resolve API URL: env var > saved config > default."""
    return (
        os.getenv("BLACKBOX_API_URL")
        or load_config().get("api_url", "")
        or "http://localhost:8000"
    )
