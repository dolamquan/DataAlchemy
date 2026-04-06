from fastapi import HTTPException

from app.db.models import get_upload_record_by_file_id
from app.engine.schemas import PlanStep, ProjectPlanResponse, UserGoal


def _contains_any(text: str, phrases: list[str]) -> bool:
	return any(phrase in text for phrase in phrases)


def infer_user_goal(user_message: str) -> UserGoal:
	msg = user_message.strip().lower()

	if _contains_any(msg, ["full pipeline", "end to end", "end-to-end", "everything", "all steps"]):
		return "full_pipeline"

	wants_preprocess = _contains_any(msg, ["preprocess", "clean", "cleaning", "feature", "transform"])
	wants_train = _contains_any(msg, ["train", "model", "classification", "regression"])
	wants_eval = _contains_any(msg, ["evaluate", "evaluation", "metrics", "accuracy", "f1", "roc"])
	wants_visualize = _contains_any(msg, ["visualize", "visualization", "chart", "plot", "graph", "insight"])
	wants_schema = _contains_any(msg, ["schema", "profile", "column", "datatype", "data type"])

	if wants_preprocess and wants_train:
		return "preprocess_and_train"
	if wants_eval and wants_train:
		return "evaluate_model"
	if wants_train:
		return "train_model"
	if wants_visualize:
		return "visualize_data"
	if wants_schema:
		return "schema_analysis"
	if wants_preprocess:
		return "preprocess_only"

	return "full_pipeline"


def build_plan_for_goal(goal: UserGoal) -> tuple[str, list[PlanStep]]:
	goal_to_plan: dict[UserGoal, tuple[str, list[PlanStep]]] = {
		"preprocess_only": (
			"The user wants data preprocessing before any downstream modeling.",
			[
				PlanStep(step="profile_dataset", agent="supervisor", status="pending"),
				PlanStep(step="preprocess_data", agent="data_preprocessing_agent", status="pending"),
				PlanStep(step="validate_preprocessing", agent="data_quality_agent", status="pending"),
			],
		),
		"visualize_data": (
			"The user wants exploratory insights and visualizations from the selected dataset.",
			[
				PlanStep(step="profile_dataset", agent="supervisor", status="pending"),
				PlanStep(step="generate_visualizations", agent="visualization_agent", status="pending"),
				PlanStep(step="summarize_insights", agent="report_agent", status="pending"),
			],
		),
		"schema_analysis": (
			"The user wants schema-focused analysis to understand columns, data quality, and structure.",
			[
				PlanStep(step="profile_dataset", agent="supervisor", status="pending"),
				PlanStep(step="analyze_schema", agent="schema_agent", status="pending"),
				PlanStep(step="report_schema_findings", agent="report_agent", status="pending"),
			],
		),
		"train_model": (
			"The user wants to train a model on the selected dataset.",
			[
				PlanStep(step="profile_dataset", agent="supervisor", status="pending"),
				PlanStep(step="prepare_training_data", agent="data_preprocessing_agent", status="pending"),
				PlanStep(step="train_model", agent="model_training_agent", status="pending"),
				PlanStep(step="evaluate_model", agent="evaluation_agent", status="pending"),
			],
		),
		"evaluate_model": (
			"The user wants model training and evaluation with quality metrics.",
			[
				PlanStep(step="profile_dataset", agent="supervisor", status="pending"),
				PlanStep(step="prepare_training_data", agent="data_preprocessing_agent", status="pending"),
				PlanStep(step="train_model", agent="model_training_agent", status="pending"),
				PlanStep(step="evaluate_model", agent="evaluation_agent", status="pending"),
				PlanStep(step="generate_report", agent="report_agent", status="pending"),
			],
		),
		"full_pipeline": (
			"The user wants a full end-to-end pipeline from profiling through reporting.",
			[
				PlanStep(step="profile_dataset", agent="supervisor", status="pending"),
				PlanStep(step="preprocess_data", agent="data_preprocessing_agent", status="pending"),
				PlanStep(step="train_model", agent="model_training_agent", status="pending"),
				PlanStep(step="evaluate_model", agent="evaluation_agent", status="pending"),
				PlanStep(step="generate_report", agent="report_agent", status="pending"),
			],
		),
		"preprocess_and_train": (
			"The user wants preprocessing followed by model training.",
			[
				PlanStep(step="profile_dataset", agent="supervisor", status="pending"),
				PlanStep(step="preprocess_data", agent="data_preprocessing_agent", status="pending"),
				PlanStep(step="train_model", agent="model_training_agent", status="pending"),
				PlanStep(step="evaluate_model", agent="evaluation_agent", status="pending"),
				PlanStep(step="generate_report", agent="report_agent", status="pending"),
			],
		),
	}

	return goal_to_plan[goal]


def build_project_plan(*, dataset_id: str, user_message: str) -> ProjectPlanResponse:
	dataset = get_upload_record_by_file_id(dataset_id)
	if dataset is None:
		raise HTTPException(status_code=404, detail="Dataset not found")

	goal = infer_user_goal(user_message)
	summary, steps = build_plan_for_goal(goal)

	return ProjectPlanResponse(
		dataset_id=dataset_id,
		user_goal=goal,
		summary=summary,
		plan=steps,
	)
