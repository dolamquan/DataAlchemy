"""Tests for agent runtime module override support."""

from __future__ import annotations

from types import SimpleNamespace

from app.engine import agent_runtime


async def _dummy_handler(payload):
    return {"status": "success", "result": {"ok": True}, "artifacts": [], "dashboard_updates": []}


def test_module_info_for_agent_prefers_yaml_override(monkeypatch) -> None:
    monkeypatch.setattr(
        agent_runtime,
        "get_agent_config",
        lambda agent_name: {
            "runtime_module": "app.agents.model_training_agent_repaired",
            "runtime_handler": "model_training_handler",
        },
    )

    module_info = agent_runtime._module_info_for_agent("model_training_agent")

    assert module_info == ("app.agents.model_training_agent_repaired", "model_training_handler")


def test_refresh_agent_after_recovery_registers_override_handler(monkeypatch) -> None:
    monkeypatch.setattr(agent_runtime, "reload_config", lambda: None)
    monkeypatch.setattr(
        agent_runtime,
        "get_agent_config",
        lambda agent_name: {
            "runtime_module": "app.agents.model_training_agent_repaired",
            "runtime_handler": "model_training_handler",
        },
    )

    fake_module = SimpleNamespace(model_training_handler=_dummy_handler)
    monkeypatch.setattr(agent_runtime.importlib, "import_module", lambda module_name: fake_module)
    monkeypatch.setattr(agent_runtime.importlib, "reload", lambda module: module)

    agent_runtime.refresh_agent_after_recovery("model_training_agent")

    assert agent_runtime._AGENT_HANDLERS["model_training_agent"] is _dummy_handler
