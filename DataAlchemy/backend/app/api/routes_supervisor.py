"""REST endpoints for the conversational supervisor agent."""

from fastapi import APIRouter

from app.engine.schemas import (
    SupervisorMessageRequest,
    SupervisorStartRequest,
    SupervisorResponse,
)
from app.engine.supervisor import send_message, start_session

router = APIRouter(prefix="/api/supervisor", tags=["supervisor"])


@router.post("/start", response_model=SupervisorResponse)
def supervisor_start(payload: SupervisorStartRequest) -> SupervisorResponse:
    return start_session(dataset_id=payload.dataset_id, user_message=payload.user_message)


@router.post("/message", response_model=SupervisorResponse)
def supervisor_message(payload: SupervisorMessageRequest) -> SupervisorResponse:
    return send_message(session_id=payload.session_id, user_message=payload.user_message)
