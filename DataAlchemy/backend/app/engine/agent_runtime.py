"""Worker agent runtime dispatch layer."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

AgentHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

_AGENT_HANDLERS: dict[str, AgentHandler] = {}


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