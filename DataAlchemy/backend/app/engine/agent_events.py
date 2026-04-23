"""In-memory event stream for live agent supervision."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

AgentEvent = dict[str, Any]

_history: dict[str, list[AgentEvent]] = {}
_subscribers: dict[str, set[asyncio.Queue[AgentEvent]]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def publish_agent_event(session_id: str | None, event: dict[str, Any]) -> None:
    if not session_id:
        return

    payload: AgentEvent = {
        "session_id": session_id,
        "timestamp": _now(),
        **event,
    }
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
