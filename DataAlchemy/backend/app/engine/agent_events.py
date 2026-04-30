"""In-memory event stream for live agent supervision."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.core.settings import LOG_AGENT_PROGRESS_TO_TERMINAL
from app.db.models import append_execution_stage_event

AgentEvent = dict[str, Any]

_history: dict[str, list[AgentEvent]] = {}
_subscribers: dict[str, set[asyncio.Queue[AgentEvent]]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _terminal_event_line(event: AgentEvent) -> str | None:
    event_type = str(event.get("type") or "unknown")
    if event_type not in {
        "coordinator_started",
        "coordinator_completed",
        "coordinator_failed",
        "step_started",
        "step_progress",
        "step_retried",
        "step_completed",
        "step_failed",
        "repair_started",
        "repair_succeeded",
        "repair_failed",
    }:
        return None

    timestamp = str(event.get("timestamp") or _now())
    agent = str(event.get("agent") or "unknown")
    step = str(event.get("step") or "-")
    status = str(event.get("status") or "-")
    message = str(event.get("message") or event_type)
    progress = event.get("progress_percent")
    progress_suffix = f" [{progress}%]" if isinstance(progress, int | float) else ""
    return f"[agent-runtime] {timestamp} | {event_type} | agent={agent} | step={step} | status={status}{progress_suffix} | {message}"


async def publish_agent_event(session_id: str | None, event: dict[str, Any]) -> None:
    if not session_id:
        return

    payload: AgentEvent = {
        "session_id": session_id,
        "timestamp": _now(),
        **event,
    }

    # Event persistence is best-effort; live websocket delivery should continue
    # even if SQLite write errors occur.
    try:
        append_execution_stage_event(session_id, payload)
    except Exception:
        pass

    if LOG_AGENT_PROGRESS_TO_TERMINAL:
        line = _terminal_event_line(payload)
        if line:
            print(line, flush=True)

    _history.setdefault(session_id, []).append(payload)

    for queue in list(_subscribers.get(session_id, set())):
        await queue.put(payload)


def get_agent_event_history(session_id: str) -> list[AgentEvent]:
    return list(_history.get(session_id, []))


async def subscribe_agent_events(session_id: str) -> asyncio.Queue[AgentEvent]:
    queue: asyncio.Queue[AgentEvent] = asyncio.Queue()
    _subscribers.setdefault(session_id, set()).add(queue)

    for event in get_agent_event_history(session_id):
        await queue.put(event)

    return queue


def unsubscribe_agent_events(session_id: str, queue: asyncio.Queue[AgentEvent]) -> None:
    subscribers = _subscribers.get(session_id)
    if not subscribers:
        return

    subscribers.discard(queue)
    if not subscribers:
        _subscribers.pop(session_id, None)


def clear_agent_event_history(session_id: str) -> None:
    _history.pop(session_id, None)
    _subscribers.pop(session_id, None)
