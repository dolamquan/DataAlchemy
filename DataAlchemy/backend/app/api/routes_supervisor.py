"""REST endpoints for the conversational supervisor agent."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.db.models import log_user_activity
from app.engine.schemas import (
    SupervisorMessageRequest,
    SupervisorStartRequest,
    SupervisorResponse,
)
from app.engine.llm_client import LLMClientError
from app.engine.supervisor import reset_user_runtime, send_message, start_session

router = APIRouter(prefix="/api/supervisor", tags=["supervisor"])


@router.post("/reset")
async def supervisor_reset(current_user: dict = Depends(get_current_user)):
    await reset_user_runtime(current_user["uid"])
    log_user_activity(
        owner_uid=current_user["uid"],
        owner_email=current_user.get("email"),
        activity_type="supervisor_reset",
        status="completed",
        resource_name="runtime",
    )
    return {"success": True}


@router.post("/start", response_model=SupervisorResponse)
async def supervisor_start(
    payload: SupervisorStartRequest,
    current_user: dict = Depends(get_current_user),
) -> SupervisorResponse:
    try:
        response = await start_session(
            dataset_id=payload.dataset_id,
            user_message=payload.user_message,
            user_uid=current_user["uid"],
        )
        log_user_activity(
            owner_uid=current_user["uid"],
            owner_email=current_user.get("email"),
            activity_type="supervisor_start",
            status="completed",
            resource_id=payload.dataset_id,
            resource_name=payload.dataset_id,
            details={"session_id": response.session_id, "response_type": response.type},
        )
        return response
    except LLMClientError as exc:
        log_user_activity(
            owner_uid=current_user["uid"],
            owner_email=current_user.get("email"),
            activity_type="supervisor_start",
            status="failed",
            resource_id=payload.dataset_id,
            resource_name=payload.dataset_id,
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/message", response_model=SupervisorResponse)
async def supervisor_message(
    payload: SupervisorMessageRequest,
    current_user: dict = Depends(get_current_user),
) -> SupervisorResponse:
    try:
        response = await send_message(
            session_id=payload.session_id,
            user_message=payload.user_message,
            dataset_id=payload.dataset_id,
            user_uid=current_user["uid"],
        )
        log_user_activity(
            owner_uid=current_user["uid"],
            owner_email=current_user.get("email"),
            activity_type="supervisor_message",
            status="completed",
            resource_id=payload.dataset_id or payload.session_id,
            resource_name=payload.dataset_id or payload.session_id,
            details={"session_id": payload.session_id, "response_type": response.type},
        )
        return response
    except LLMClientError as exc:
        log_user_activity(
            owner_uid=current_user["uid"],
            owner_email=current_user.get("email"),
            activity_type="supervisor_message",
            status="failed",
            resource_id=payload.dataset_id or payload.session_id,
            resource_name=payload.dataset_id or payload.session_id,
            details={"session_id": payload.session_id, "error": str(exc)},
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
