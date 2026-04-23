"""Worker agent runtime dispatch layer."""

from __future__ import annotations

import importlib
from collections.abc import Awaitable, Callable
from typing import Any

from app.engine.registry import reload_config

AgentHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

_AGENT_HANDLERS: dict[str, AgentHandler] = {}

_REAL_AGENT_MODULES: dict[str, tuple[str, str]] = {
    "data_quality_agent": ("app.agents.data_quality_agent", "data_quality_handler"),
    "data_preprocessing_agent": ("app.agents.data_preprocessing_agent", "data_preprocessing_handler"),
    "model_training_agent": ("app.agents.model_training_agent", "model_training_handler"),
    "evaluation_agent": ("app.agents.evaluation_agent", "evaluation_handler"),
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


def refresh_agent_after_recovery(agent_name: str) -> None:
    """Refresh YAML config and re-register a patched real agent module."""
    reload_config()
    module_info = _REAL_AGENT_MODULES.get(agent_name)
    if module_info is None:
        return

    module_name, handler_name = module_info
    module = importlib.import_module(module_name)
    module = importlib.reload(module)
    register_agent_handler(agent_name, getattr(module, handler_name))


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


# Register real agent handlers — imported here so registration happens at module load time.
from app.agents.data_quality_agent import data_quality_handler  # noqa: E402
from app.agents.data_preprocessing_agent import data_preprocessing_handler  # noqa: E402
from app.agents.evaluation_agent import evaluation_handler  # noqa: E402
from app.agents.model_training_agent import model_training_handler  # noqa: E402

register_agent_handler("data_quality_agent", data_quality_handler)
register_agent_handler("data_preprocessing_agent", data_preprocessing_handler)
register_agent_handler("model_training_agent", model_training_handler)
register_agent_handler("evaluation_agent", evaluation_handler)
