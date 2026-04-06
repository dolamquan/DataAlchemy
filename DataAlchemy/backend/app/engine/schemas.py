from typing import Literal

from pydantic import BaseModel, Field


PlanStatus = Literal["pending", "in_progress", "completed", "blocked"]
UserGoal = Literal[
	"preprocess_only",
	"visualize_data",
	"schema_analysis",
	"train_model",
	"evaluate_model",
	"full_pipeline",
	"preprocess_and_train",
]


class ProjectPlanRequest(BaseModel):
	dataset_id: str = Field(..., min_length=1, max_length=256)
	user_message: str = Field(..., min_length=3, max_length=4000)


class PlanStep(BaseModel):
	step: str
	agent: str
	status: PlanStatus = "pending"


class ProjectPlanResponse(BaseModel):
	dataset_id: str
	user_goal: UserGoal
	summary: str
	plan: list[PlanStep]
