from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.engine.schemas import ProjectPlanRequest, ProjectPlanResponse
from app.services.project_service import build_project_plan

router = APIRouter(prefix="/api", tags=["projects"])


@router.post("/projects/plan", response_model=ProjectPlanResponse)
async def create_project_plan(
    payload: ProjectPlanRequest,
    current_user: dict = Depends(get_current_user),
) -> ProjectPlanResponse:
    return await build_project_plan(
        dataset_id=payload.dataset_id,
        user_message=payload.user_message,
        user_uid=current_user["uid"],
    )
