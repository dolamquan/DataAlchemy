"""Agent configuration registry — loads and caches agents.yaml."""

from __future__ import annotations

from copy import deepcopy
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

    agent_config = deepcopy(agents[agent_name])
    model_name = agent_config.get("model")
    model_aliases = config.get("models", {})
    if isinstance(model_name, str) and model_name in model_aliases:
        resolved_model = model_aliases[model_name]
        if isinstance(resolved_model, dict):
            concrete_model = resolved_model.get("model")
            if isinstance(concrete_model, str) and concrete_model.strip():
                agent_config["model"] = concrete_model

    return agent_config


def reload_config() -> None:
    """Clear the cache and force a fresh load from disk. Useful during development."""
    _load_config.cache_clear()
