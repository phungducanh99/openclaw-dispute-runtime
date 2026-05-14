from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from paths import CONFIG_ROOT


def load_config(name: str = "production.json") -> dict[str, Any]:
    config_path = CONFIG_ROOT / name
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    return json.loads(config_path.read_text(encoding="utf-8"))
