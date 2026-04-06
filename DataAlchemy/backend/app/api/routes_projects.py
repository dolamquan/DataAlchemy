from fastapi import APIRouter

from app.engine.schemas import ProjectPlanRequest, ProjectPlanResponse
from app.services.project_service import build_project_plan

router = APIRouter(prefix="/api", tags=["projects"])


@router.post("/projects/plan", response_model=ProjectPlanResponse)
def create_project_plan(payload: ProjectPlanRequest) -> ProjectPlanResponse:
    return build_project_plan(dataset_id=payload.dataset_id, user_message=payload.user_message)
