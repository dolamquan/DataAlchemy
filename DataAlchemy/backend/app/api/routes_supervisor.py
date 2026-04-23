"""REST endpoints for the conversational supervisor agent."""

from fastapi import APIRouter, HTTPException

from app.engine.schemas import (
    SupervisorMessageRequest,
    SupervisorStartRequest,
    SupervisorResponse,
)
from app.engine.llm_client import LLMClientError
from app.engine.supervisor import send_message, start_session

router = APIRouter(prefix="/api/supervisor", tags=["supervisor"])


@router.post("/start", response_model=SupervisorResponse)
async def supervisor_start(payload: SupervisorStartRequest) -> SupervisorResponse:
    try:
        return await start_session(dataset_id=payload.dataset_id, user_message=payload.user_message)
    except LLMClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/message", response_model=SupervisorResponse)
async def supervisor_message(payload: SupervisorMessageRequest) -> SupervisorResponse:
    try:
        return await send_message(
            session_id=payload.session_id,
            user_message=payload.user_message,
            dataset_id=payload.dataset_id,
        )
    except LLMClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
