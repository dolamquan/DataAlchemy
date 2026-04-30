"""Tests for agent registry config resolution."""

from __future__ import annotations

from app.engine import registry


def test_get_agent_config_resolves_model_alias() -> None:
    registry.reload_config()

    config = registry.get_agent_config("supervisor")

    assert config["model"] == "gpt-5.1"


def test_get_agent_config_returns_copy() -> None:
    registry.reload_config()

    config = registry.get_agent_config("supervisor")
    config["model"] = "mutated"

    fresh = registry.get_agent_config("supervisor")

    assert fresh["model"] == "gpt-5.1"
