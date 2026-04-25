"""WebSocket endpoints for live agent supervision."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import authenticate_websocket
from app.engine.agent_events import subscribe_agent_events, unsubscribe_agent_events
from app.engine.supervisor import user_can_access_session

router = APIRouter(tags=["agent-events"])


@router.websocket("/ws/agents/{session_id}")
async def agent_events_socket(websocket: WebSocket, session_id: str) -> None:
    current_user = await authenticate_websocket(websocket)
    if not user_can_access_session(session_id, current_user["uid"]):
        await websocket.close(code=4403, reason="Forbidden")
        return
    await websocket.accept()
    queue = await subscribe_agent_events(session_id)

    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        unsubscribe_agent_events(session_id, queue)
    except Exception:
        unsubscribe_agent_events(session_id, queue)
        raise
