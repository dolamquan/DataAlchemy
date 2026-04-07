"""Agent configuration registry — loads and caches agents.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CONFIG_PATH = Path(__file__).parents[3] / "backend"/ "configs" / "agents.yaml"


@lru_cache(maxsize=1)
def _load_config() -> dict[str, Any]:
    """Load and cache agents.yaml. Parsed once at first call."""
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_agent_config(agent_name: str) -> dict[str, Any]:
    """Return the config block for a named agent. Raises KeyError if not found."""
    config = _load_config()
    agents = config.get("agents", {})
    if agent_name not in agents:
        raise KeyError(f"Agent '{agent_name}' not found in agents.yaml")
    return agents[agent_name]


def reload_config() -> None:
    """Clear the cache and force a fresh load from disk. Useful during development."""
    _load_config.cache_clear()
