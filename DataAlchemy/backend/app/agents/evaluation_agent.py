"""Evaluation Agent - scores a trained model against a CSV dataset.

The evaluator expects to run after model_training_agent. It loads the model
artifact from prior_results, locates the same preprocessed CSV used for
training, recomputes predictions, and writes an evaluation report JSON.
"""

from __future__ import annotations

import math
import traceback
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)

from app.core.settings import UPLOAD_DIR
from app.engine.registry import get_agent_config
from app.services.artifacts import safe_artifact_file_id, write_json_artifact
from app.services.storage import resolve_upload_path_from_db


def _resolve_config(payload_config: dict[str, Any]) -> dict[str, Any]:
    """Merge YAML defaults with caller-supplied overrides."""
    try:
        agent_cfg = get_agent_config("evaluation_agent")
        defaults: dict[str, Any] = agent_cfg.get("defaults", {})
    except KeyError:
        defaults = {}

    resolved: dict[str, Any] = {
        "target_column": None,
        "task_type": None,
        "metrics": None,
        "positive_label": None,
    }
    resolved.update(defaults)
    resolved.update({k: v for k, v in payload_config.items() if v is not None})
    return resolved


def _locate_evaluation_csv(dataset_id: str, prior_results: list[dict[str, Any]]) -> Path:
    """Return the CSV path to evaluate on, preferring preprocessed data."""
    for entry in prior_results:
        if entry.get("agent") == "data_preprocessing_agent":
            file_id = (entry.get("result") or {}).get("preprocessed_file_id")
            if file_id:
                candidate = UPLOAD_DIR / file_id
                if candidate.exists():
                    return candidate

    stem = dataset_id if dataset_id.endswith(".csv") else dataset_id
    convention = UPLOAD_DIR / f"preprocessed_{stem}"
    if not str(convention).endswith(".csv"):
        convention = Path(str(convention) + ".csv")
    if convention.exists():
        return convention

    try:
        return resolve_upload_path_from_db(dataset_id)
    except FileNotFoundError:
        pass

    raise ValueError(
        f"Cannot locate evaluation CSV for dataset '{dataset_id}'. "
        "Run preprocessing first or upload the dataset again."
    )


def _find_training_result(prior_results: list[dict[str, Any]]) -> dict[str, Any]:
    for entry in reversed(prior_results):
        if entry.get("agent") == "model_training_agent":
            result = entry.get("result") or {}
            if isinstance(result, dict):
                return result
    return {}


def _resolve_model_path(
    dataset_id: str,
    cfg: dict[str, Any],
    training_result: dict[str, Any],
    prior_results: list[dict[str, Any]],
) -> Path:
    explicit = cfg.get("model_file_id") or cfg.get("model_path")
    candidates: list[Path] = []

    if explicit:
        explicit_path = Path(str(explicit))
        candidates.append(explicit_path if explicit_path.is_absolute() else UPLOAD_DIR / explicit_path)

    model_file_id = training_result.get("model_file_id")
    if model_file_id:
        candidates.append(UPLOAD_DIR / str(model_file_id))

    for entry in reversed(prior_results):
        for artifact in entry.get("artifacts") or []:
            if artifact.get("type") == "joblib" or artifact.get("name") == "trained_model.joblib":
                if artifact.get("path"):
                    candidates.append(Path(str(artifact["path"])))
                if artifact.get("file_id"):
                    candidates.append(UPLOAD_DIR / str(artifact["file_id"]))

    fallback = f"model_{dataset_id}"
    if not fallback.endswith(".joblib"):
        fallback += ".joblib"
    candidates.append(UPLOAD_DIR / fallback)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate

    checked = [str(path) for path in candidates]
    raise ValueError(f"Cannot locate trained model artifact. Checked: {checked}")


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def _split_features_target(df: pd.DataFrame, target_column: str) -> tuple[pd.DataFrame, pd.Series]:
    y = df[target_column].copy()
    X = df.drop(columns=[target_column])
    X = X.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return X, y


def _detect_task_type(y: pd.Series, override: str | None, training_result: dict[str, Any]) -> str:
    if override in {"classification", "regression"}:
        return override

    trained_task_type = training_result.get("task_type")
    if trained_task_type in {"classification", "regression"}:
        return str(trained_task_type)

    if pd.api.types.is_string_dtype(y) or pd.api.types.is_object_dtype(y):
        return "classification"
    if pd.api.types.is_integer_dtype(y) and y.nunique() <= 10:
        return "classification"
    if pd.api.types.is_float_dtype(y) and y.nunique() <= 10:
        return "classification"
    return "regression"


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _classification_metrics(model: Any, X: pd.DataFrame, y: pd.Series, positive_label: Any = None) -> dict[str, Any]:
    y_pred = model.predict(X)
    labels = sorted({str(value) for value in list(y.dropna().unique()) + list(pd.Series(y_pred).dropna().unique())})
    cm = confusion_matrix(y.astype(str), pd.Series(y_pred).astype(str), labels=labels)

    metrics: dict[str, Any] = {
        "accuracy": _finite_float(accuracy_score(y, y_pred)),
        "balanced_accuracy": _finite_float(balanced_accuracy_score(y, y_pred)),
        "f1_macro": _finite_float(f1_score(y, y_pred, average="macro", zero_division=0)),
        "precision_macro": _finite_float(precision_score(y, y_pred, average="macro", zero_division=0)),
        "recall_macro": _finite_float(recall_score(y, y_pred, average="macro", zero_division=0)),
        "labels": labels,
        "confusion_matrix": cm.tolist(),
    }

    if y.nunique() == 2 and hasattr(model, "predict_proba"):
        try:
            probabilities = model.predict_proba(X)
            classes = list(getattr(model, "classes_", []))
            label = positive_label if positive_label is not None else classes[-1]
            class_index = classes.index(label)
            metrics["roc_auc"] = _finite_float(roc_auc_score(y, probabilities[:, class_index]))
            metrics["positive_label"] = label
        except Exception as exc:
            metrics["roc_auc_error"] = str(exc)

    return metrics


def _regression_metrics(model: Any, X: pd.DataFrame, y: pd.Series) -> dict[str, Any]:
    y_numeric = pd.to_numeric(y, errors="coerce")
    valid_mask = y_numeric.notna()
    if not valid_mask.any():
        raise ValueError("Regression target contains no numeric values to evaluate.")

    X_valid = X.loc[valid_mask]
    y_valid = y_numeric.loc[valid_mask]
    y_pred = model.predict(X_valid)
    mse = mean_squared_error(y_valid, y_pred)
    return {
        "mae": _finite_float(mean_absolute_error(y_valid, y_pred)),
        "rmse": _finite_float(math.sqrt(mse)),
        "r2": _finite_float(r2_score(y_valid, y_pred)),
    }


async def evaluation_handler(payload: dict[str, Any]) -> dict[str, Any]:
    """Async handler registered with agent_runtime for 'evaluation_agent'."""
    step: str = payload.get("step", "evaluate_model")
    dataset_id: str = payload.get("dataset_id", "")
    cfg = _resolve_config(payload.get("config") or {})
    prior_results: list[dict[str, Any]] = payload.get("prior_results") or []
    training_result = _find_training_result(prior_results)

    try:
        csv_path = _locate_evaluation_csv(dataset_id, prior_results)
        model_path = _resolve_model_path(dataset_id, cfg, training_result, prior_results)
    except ValueError as exc:
        return _failed(step, str(exc))

    try:
        df = _read_csv(csv_path)
    except Exception as exc:
        return _failed(step, f"Could not read evaluation CSV: {exc}\n{traceback.format_exc()}")

    if df.empty:
        return _failed(step, "CSV file contains no data rows.")

    target_column = cfg.get("target_column") or training_result.get("target_column")
    if not target_column:
        return _failed(step, "Target column is required for evaluation. Run model training first or set target_column.")
    if target_column not in df.columns:
        return _failed(
            step,
            f"Target column '{target_column}' not found in evaluation dataset. "
            f"Available columns: {sorted(df.columns.tolist())}",
        )

    X, y = _split_features_target(df, str(target_column))
    if X.empty:
        return _failed(step, "No feature columns remain after separating the target column.")
    if y.isnull().all():
        return _failed(step, f"Target column '{target_column}' contains only null values.")

    try:
        model = joblib.load(model_path)
    except Exception as exc:
        return _failed(step, f"Could not load trained model: {exc}\n{traceback.format_exc()}")

    task_type = _detect_task_type(y, cfg.get("task_type"), training_result)
    try:
        if task_type == "classification":
            metrics = _classification_metrics(model, X, y, cfg.get("positive_label"))
            primary_metric = "accuracy"
            primary_score = metrics.get(primary_metric)
        else:
            metrics = _regression_metrics(model, X, y)
            primary_metric = "rmse"
            primary_score = metrics.get(primary_metric)
    except Exception as exc:
        return _failed(step, f"Model evaluation failed: {exc}\n{traceback.format_exc()}")

    result_data: dict[str, Any] = {
        "task_type": task_type,
        "target_column": target_column,
        "n_samples": int(len(df)),
        "n_features": int(X.shape[1]),
        "model_file_id": model_path.name,
        "primary_metric": primary_metric,
        "primary_score": primary_score,
        "metrics": metrics,
    }

    report_file_id = safe_artifact_file_id("evaluation_report", dataset_id, ".json")
    report_path = write_json_artifact(report_file_id, result_data)

    return {
        "status": "success",
        "result": result_data,
        "artifacts": [
            {
                "name": "evaluation_report.json",
                "type": "json",
                "path": str(report_path),
                "file_id": report_file_id,
            }
        ],
        "dashboard_updates": [
            {
                "agent": "evaluation_agent",
                "step": step,
                "status": "completed",
                "message": (
                    f"Evaluated {task_type} model on {len(df)} rows; "
                    f"{primary_metric}={primary_score}."
                ),
            }
        ],
    }


def _failed(step: str, message: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "result": {"error": message},
        "artifacts": [],
        "dashboard_updates": [
            {
                "agent": "evaluation_agent",
                "step": step,
                "status": "failed",
                "message": message,
            }
        ],
    }
