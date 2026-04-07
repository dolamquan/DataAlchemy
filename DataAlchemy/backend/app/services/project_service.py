from fastapi import HTTPException

from app.engine.schemas import ProjectPlanResponse
from app.engine.supervisor import start_session


def build_project_plan(*, dataset_id: str, user_message: str) -> ProjectPlanResponse:
    """Compatibility adapter for the legacy /api/projects/plan endpoint.

    Planning is now owned by the LLM supervisor. This wrapper starts a
    supervisor session and returns the generated plan payload.
    """
    response = start_session(dataset_id=dataset_id, user_message=user_message)
    if response.plan is None:
        raise HTTPException(status_code=502, detail="Supervisor did not return a plan")
    return response.plan
