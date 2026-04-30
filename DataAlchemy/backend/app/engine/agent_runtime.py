"""Worker agent runtime dispatch layer."""

from __future__ import annotations

import importlib
from collections.abc import Awaitable, Callable
from typing import Any

from app.engine.registry import get_agent_config, reload_config

AgentHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

_AGENT_HANDLERS: dict[str, AgentHandler] = {}

_REAL_AGENT_MODULES: dict[str, tuple[str, str]] = {
    "data_quality_agent": ("app.agents.data_quality_agent", "data_quality_handler"),
    "data_preprocessing_agent": ("app.agents.data_preprocessing_agent", "data_preprocessing_handler"),
    "model_training_agent": ("app.agents.model_training_agent", "model_training_handler"),
    "evaluation_agent": ("app.agents.evaluation_agent", "evaluation_handler"),
    "report_agent": ("app.agents.report_agent", "report_handler"),
}


async def _default_handler(payload: dict[str, Any]) -> dict[str, Any]:
    """Default placeholder worker behavior for known agents.

    Real agent implementations can replace these handlers via
    register_agent_handler without changing coordinator logic.
    """
    agent_name = str(payload.get("agent") or "unknown_agent")
    step = payload.get("step")
    return {
        "status": "success",
        "result": {
            "agent": agent_name,
            "step": step,
            "message": "Step completed by default runtime handler",
        },
        "artifacts": [],
        "dashboard_updates": [
            {
                "agent": agent_name,
                "step": step,
                "status": "completed",
                "message": "Default handler completed step",
            }
        ],
    }


def _register_default_handlers() -> None:
    for name in [
        "supervisor",
        "data_preprocessing_agent",
        "data_quality_agent",
        "visualization_agent",
        "schema_agent",
        "model_training_agent",
        "evaluation_agent",
        "report_agent",
    ]:
        _AGENT_HANDLERS.setdefault(name, _default_handler)


def register_agent_handler(agent_name: str, handler: AgentHandler) -> None:
    """Register an async handler for a worker agent name."""
    _AGENT_HANDLERS[agent_name] = handler


def _module_info_for_agent(agent_name: str) -> tuple[str, str] | None:
    default = _REAL_AGENT_MODULES.get(agent_name)
    try:
        agent_config = get_agent_config(agent_name)
    except KeyError:
        return default

    module_name = agent_config.get("runtime_module")
    handler_name = agent_config.get("runtime_handler")
    if isinstance(module_name, str) and module_name.strip() and isinstance(handler_name, str) and handler_name.strip():
        return module_name, handler_name
    return default


def _load_agent_handler(agent_name: str, *, reload_module: bool) -> AgentHandler | None:
    module_info = _module_info_for_agent(agent_name)
    if module_info is None:
        return None

    module_name, handler_name = module_info
    module = importlib.import_module(module_name)
    if reload_module:
        module = importlib.reload(module)
    return getattr(module, handler_name)


def _register_real_handlers(*, reload_modules: bool) -> None:
    for agent_name in _REAL_AGENT_MODULES:
        handler = _load_agent_handler(agent_name, reload_module=reload_modules)
        if handler is not None:
            register_agent_handler(agent_name, handler)


def refresh_agent_after_recovery(agent_name: str) -> None:
    """Refresh YAML config and re-register a patched real agent module."""
    reload_config()
    handler = _load_agent_handler(agent_name, reload_module=True)
    if handler is None:
        return
    register_agent_handler(agent_name, handler)


async def run_agent(agent_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch execution to a worker agent.

    Structured return shape:
      {
        "status": "success|failed",
        "result": {...} | None,
        "artifacts": [],
        "dashboard_updates": []
      }
    """
    _register_default_handlers()
    handler = _AGENT_HANDLERS.get(agent_name)
    if handler is None:
        return {
            "status": "failed",
            "result": {
                "error": f"No runtime handler registered for agent '{agent_name}'",
                "payload": payload,
            },
            "artifacts": [],
            "dashboard_updates": [
                {
                    "agent": agent_name,
                    "step": payload.get("step"),
                    "status": "failed",
                    "message": "Missing agent handler",
                }
            ],
        }

    result = await handler(payload)
    return {
        "status": result.get("status", "success"),
        "result": result.get("result"),
        "artifacts": result.get("artifacts", []),
        "dashboard_updates": result.get("dashboard_updates", []),
    }


_register_real_handlers(reload_modules=False)
