"""Model Training Agent — selects, tunes, and trains an ML model on a CSV dataset.

Flow:
  1. Locate the training CSV (preprocessed file preferred via prior_results)
  2. Infer target column if not provided in config
  3. Detect task type (classification | regression)
  4. Select candidate models based on dataset size and task type
  5. Run Optuna HPO per candidate (n_trials scales with dataset size)
  6. Train final model on full data with best params
  7. Save model to disk (joblib) and return artifacts

The trained model is saved to the uploads directory as
  model_{dataset_id}.joblib
and its path is returned in the artifacts list.
"""

from __future__ import annotations

import re
import time
import traceback
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import optuna
import pandas as pd
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_score
from lightgbm import LGBMClassifier, LGBMRegressor
from xgboost import XGBClassifier, XGBRegressor

from app.core.settings import UPLOAD_DIR
from app.db.models import get_upload_schema_by_file_id
from app.engine.agent_events import publish_agent_event
from app.engine.registry import get_agent_config
from app.services.artifacts import safe_artifact_file_id, write_json_artifact
from app.services.runtime_interrupt import UserInterruptRequested, is_interrupted, raise_if_interrupted
from app.services.storage import resolve_upload_path_from_db

optuna.logging.set_verbosity(optuna.logging.WARNING)


async def _publish_progress(
    session_id: str | None,
    *,
    step: str,
    percent: int,
    message: str,
) -> None:
    await publish_agent_event(
        session_id,
        {
            "type": "step_progress",
            "step": step,
            "agent": "model_training_agent",
            "status": "in_progress",
            "message": message,
            "progress_percent": percent,
        },
    )

# ---------------------------------------------------------------------------
# Known target-column names (ordered by priority)
# ---------------------------------------------------------------------------

_TARGET_NAMES: frozenset[str] = frozenset({
    "target", "label", "y", "class", "churn", "exited",
    "fraud", "price", "outcome", "survived", "default",
    "result", "score", "final_score",
})

_WEEK_COLUMN_RE = re.compile(r"^week_(\d+)$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------

def _resolve_config(payload_config: dict[str, Any]) -> dict[str, Any]:
    """Merge agent defaults from agents.yaml with caller-supplied overrides."""
    try:
        #Get the config from agents.yaml for this agent, and extract any defaults
        agent_cfg = get_agent_config("model_training_agent")
        defaults: dict[str, Any] = agent_cfg.get("defaults", {})
    except KeyError:
        defaults = {}

    resolved: dict[str, Any] = {
        "task_type": None,
        "target_column": None,
        "model": None,
        "metric": None,
        "n_trials": None,
        "cv_folds": 5,
        "random_state": 42,
        "hpo_timeout_seconds": None,
    }
    resolved.update(defaults)

    # Override with any non-null values from the payload config
    resolved.update({k: v for k, v in payload_config.items() if v is not None})
    return resolved


# ---------------------------------------------------------------------------
# File location
# ---------------------------------------------------------------------------

def _locate_training_csv(dataset_id: str, prior_results: list[dict[str, Any]]) -> Path:
    """Return the path to the CSV to train on.

    Priority:
      1. preprocessed_file_id from a prior data_preprocessing_agent result
      2. UPLOAD_DIR/preprocessed_{dataset_id}[.csv] by convention
      3. Stored path from the uploads DB record
      4. UPLOAD_DIR/{dataset_id} direct fallback
    """
    # 1. From prior_results (result from preprocessing agent)
    for entry in prior_results:
        if entry.get("agent") == "data_preprocessing_agent":
            file_id = (entry.get("result") or {}).get("preprocessed_file_id")
            if file_id:
                candidate = UPLOAD_DIR / file_id
                if candidate.exists():
                    return candidate

    # 2. Convention fallback (input from function caller)
    stem = dataset_id if dataset_id.endswith(".csv") else dataset_id
    convention = UPLOAD_DIR / f"preprocessed_{stem}"
    if not str(convention).endswith(".csv"):
        convention = Path(str(convention) + ".csv")
    if convention.exists():
        return convention

    # 3. DB stored path, restoring original upload bytes if disk copy was removed
    try:
        return resolve_upload_path_from_db(dataset_id)
    except FileNotFoundError:
        pass

    raise ValueError(
        f"Cannot locate training CSV for dataset '{dataset_id}'. "
        "Ensure the dataset was uploaded or preprocessing ran first."
    )


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def _read_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


# ---------------------------------------------------------------------------
# Target inference
# ---------------------------------------------------------------------------

def _infer_target_column(df: pd.DataFrame, schema_profile: dict[str, Any] | None) -> str:
    """Infer the most likely target column from the schema profile.

    Priority:
      1. Column name matches a known target-name keyword
      2. Binary integer column (unique_count == 2)
      3. Low-cardinality integer/categorical column (2 <= unique_count <= 10)
    """
    df_cols: set[str] = set(df.columns)
    columns: list[dict[str, Any]] = (schema_profile or {}).get("columns", [])

    # 1. Named match (check DataFrame columns directly first, then schema)
    for name in _TARGET_NAMES:
        if name in df_cols:
            return name

    week_columns = [
        (int(match.group(1)), column)
        for column in df.columns
        if (match := _WEEK_COLUMN_RE.match(str(column)))
    ]
    if week_columns:
        return max(week_columns)[1]

    # 2. Binary integer column
    for col in columns:
        col_name = col.get("name", "")
        if col_name not in df_cols:
            continue
        if col.get("inferred_dtype") in {"integer", "float"} and col.get("unique_count") == 2:
            return col_name

    # 3. Low-cardinality categorical/integer
    for col in columns:
        col_name = col.get("name", "")
        if col_name not in df_cols:
            continue
        dtype = col.get("inferred_dtype", "")
        unique = col.get("unique_count", 0)
        non_null = col.get("non_null_count", 0)
        if dtype in {"integer", "categorical", "string"} and 2 <= unique <= 10 and non_null > 0:
            return col_name

    candidates = sorted(df_cols)
    raise ValueError(
        "Cannot infer target column. No column matches known target names or "
        f"low-cardinality patterns. Available columns: {candidates}. "
        "Set 'target_column' in the step config."
    )


# ---------------------------------------------------------------------------
# Task type detection
# ---------------------------------------------------------------------------

def _detect_task_type(y: pd.Series, override: str | None) -> str:
    """Return 'classification' or 'regression'."""
    if override in {"classification", "regression"}:
        return override

    # String / object dtype (includes pandas StringDtype) → always classification
    if pd.api.types.is_string_dtype(y) or pd.api.types.is_object_dtype(y):
        return "classification"

    # Integer with few unique values → classification
    if pd.api.types.is_integer_dtype(y) and y.nunique() <= 10:
        return "classification"

    # Float with few unique values (e.g. 0.0 / 1.0 binary) → classification
    if pd.api.types.is_float_dtype(y) and y.nunique() <= 10:
        return "classification"

    return "regression"


# ---------------------------------------------------------------------------
# Feature / target split
# ---------------------------------------------------------------------------

def _split_features_target(df: pd.DataFrame, target_column: str) -> tuple[pd.DataFrame, pd.Series]:
    y = df[target_column].copy()
    X = df.drop(columns=[target_column])
    # Coerce all feature columns to numeric; fill residual NaNs with 0
    X = X.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return X, y


# ---------------------------------------------------------------------------
# Metric selection
# ---------------------------------------------------------------------------

def _pick_metric(task_type: str, y: pd.Series) -> str:
    if task_type == "regression":
        return "neg_root_mean_squared_error"
    # Classification
    if y.nunique() == 2:
        return "roc_auc"
    return "f1_macro"


# ---------------------------------------------------------------------------
# Model selection (rule-based)
# ---------------------------------------------------------------------------

def _select_candidate_models(task_type: str, n_samples: int, n_features: int) -> list[str]:
    """Return a shortlist of model names based on task type and dataset size."""
    if task_type == "classification":
        if n_samples < 1_000:
            return ["LogisticRegression", "RandomForestClassifier"]
        if n_samples < 10_000:
            return ["RandomForestClassifier", "GradientBoostingClassifier", "LGBMClassifier"]
        return ["LGBMClassifier", "XGBClassifier"]
    else:  # regression
        if n_samples < 1_000:
            return ["Ridge", "RandomForestRegressor"]
        if n_samples < 10_000:
            return ["RandomForestRegressor", "GradientBoostingRegressor", "LGBMRegressor"]
        return ["LGBMRegressor", "XGBRegressor"]


# ---------------------------------------------------------------------------
# HPO budget
# ---------------------------------------------------------------------------

def _scale_n_trials(n_samples: int) -> int:
    """Return number of Optuna trials scaled to dataset size."""
    if n_samples < 20:
        return 5
    if n_samples < 1_000:
        return 50
    if n_samples < 10_000:
        return 30
    if n_samples < 100_000:
        return 15
    return 10


# ---------------------------------------------------------------------------
# CV builder - Pick a cross-validation strategy based on task (Classification -> StratifiedKFold / Regression -> KFold)
# ---------------------------------------------------------------------------

def _build_cv(task_type: str, n_splits: int = 5):
    if task_type == "classification":
        return StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    return KFold(n_splits=n_splits, shuffle=True, random_state=42)


def _resolve_cv_folds(task_type: str, y: pd.Series, requested_folds: int) -> int:
    """Cap CV folds to the number of splits the target distribution supports."""
    requested_folds = max(2, requested_folds)
    if task_type == "classification":
        class_counts = y.value_counts(dropna=False)
        if len(class_counts) < 2:
            raise ValueError("Classification requires at least 2 target classes.")

        min_class_count = int(class_counts.min())
        if min_class_count < 2:
            rare_classes = sorted(str(label) for label, count in class_counts.items() if count < 2)
            raise ValueError(
                "Classification requires at least 2 examples per class for cross-validation. "
                f"Classes with too few examples: {rare_classes}."
            )
        return min(requested_folds, min_class_count)

    if len(y) < 2:
        raise ValueError("Regression requires at least 2 rows for cross-validation.")
    return min(requested_folds, len(y))


# ---------------------------------------------------------------------------
# Optuna search spaces - Pick hyperparameters to tune for each model
# ---------------------------------------------------------------------------

def _get_search_space(trial: optuna.Trial, model_name: str) -> dict[str, Any]:
    """Return hyperparameter suggestions for a given model."""
    if model_name == "LogisticRegression":
        return {
            "C": trial.suggest_float("C", 1e-3, 1e2, log=True),
        }
    if model_name == "Ridge":
        return {
            "alpha": trial.suggest_float("alpha", 1e-3, 1e2, log=True),
        }
    if model_name in {"RandomForestClassifier", "RandomForestRegressor"}:
        return {
            "n_estimators": trial.suggest_int("n_estimators", 50, 300, step=50),
            "max_depth": trial.suggest_int("max_depth", 3, 20),
            "min_samples_split": trial.suggest_int("min_samples_split", 2, 10),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 5),
        }
    if model_name in {"GradientBoostingClassifier", "GradientBoostingRegressor"}:
        return {
            "n_estimators": trial.suggest_int("n_estimators", 50, 300),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        }
    if model_name in {"LGBMClassifier", "LGBMRegressor"}:
        return {
            "n_estimators": trial.suggest_int("n_estimators", 50, 500),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 15, 127),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 50),
        }
    if model_name in {"XGBClassifier", "XGBRegressor"}:
        return {
            "n_estimators": trial.suggest_int("n_estimators", 50, 500),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        }
    raise ValueError(f"Unknown model name: '{model_name}'")


# ---------------------------------------------------------------------------
# Model factory
# ---------------------------------------------------------------------------

def _build_model(model_name: str, params: dict[str, Any], random_state: int) -> Any:
    """Instantiate a model from its name and hyperparameters."""
    rs = random_state
    factories: dict[str, Any] = {
        "LogisticRegression": lambda p: LogisticRegression(
            **p, random_state=rs, max_iter=500, solver="lbfgs"
        ),
        "Ridge": lambda p: Ridge(**p),
        "RandomForestClassifier": lambda p: RandomForestClassifier(
            **p, random_state=rs, n_jobs=-1
        ),
        "RandomForestRegressor": lambda p: RandomForestRegressor(
            **p, random_state=rs, n_jobs=-1
        ),
        "GradientBoostingClassifier": lambda p: GradientBoostingClassifier(
            **p, random_state=rs
        ),
        "GradientBoostingRegressor": lambda p: GradientBoostingRegressor(
            **p, random_state=rs
        ),
        "LGBMClassifier": lambda p: LGBMClassifier(**p, random_state=rs, verbose=-1),
        "LGBMRegressor": lambda p: LGBMRegressor(**p, random_state=rs, verbose=-1),
        "XGBClassifier": lambda p: XGBClassifier(**p, random_state=rs, verbosity=0),
        "XGBRegressor": lambda p: XGBRegressor(**p, random_state=rs, verbosity=0),
    }
    if model_name not in factories:
        raise ValueError(f"Unknown model name: '{model_name}'")
    return factories[model_name](params)


# ---------------------------------------------------------------------------
# HPO
# ---------------------------------------------------------------------------

def _run_hpo(
    X: pd.DataFrame,
    y: pd.Series,
    model_name: str,
    metric: str,
    n_trials: int,
    cv: Any,
    random_state: int,
    session_id: str | None = None,
    timeout: float | None = None,
) -> tuple[dict[str, Any], float]:
    """Run Optuna HPO for one candidate model; return (best_params, best_cv_score)."""

    def objective(trial: optuna.Trial) -> float:
        raise_if_interrupted(session_id, context="Training interrupted by user.")
        params = _get_search_space(trial, model_name)
        model = _build_model(model_name, params, random_state)
        scores = cross_val_score(model, X, y, cv=cv, scoring=metric, error_score=0.0)
        return float(scores.mean())

    pruner = optuna.pruners.MedianPruner(n_startup_trials=5)
    sampler = optuna.samplers.TPESampler(seed=random_state)
    study = optuna.create_study(direction="maximize", pruner=pruner, sampler=sampler)
    study.optimize(
        objective,
        n_trials=n_trials,
        timeout=timeout,
        show_progress_bar=False,
        callbacks=[lambda study, trial: study.stop() if is_interrupted(session_id) else None],
    )

    raise_if_interrupted(session_id, context="Training interrupted by user.")

    return study.best_params, study.best_value


# ---------------------------------------------------------------------------
# Final training + persistence
# ---------------------------------------------------------------------------

def _fit_final_model(
    X: pd.DataFrame,
    y: pd.Series,
    model_name: str,
    best_params: dict[str, Any],
    random_state: int,
) -> Any:
    model = _build_model(model_name, best_params, random_state)
    model.fit(X, y)
    return model


def _save_model(model: Any, out_path: Path) -> None:
    joblib.dump(model, out_path)


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------

async def model_training_handler(payload: dict[str, Any]) -> dict[str, Any]:
    """Async handler registered with agent_runtime for 'model_training_agent'."""
    step: str = payload.get("step", "train_model")
    dataset_id: str = payload.get("dataset_id", "")
    session_id: str | None = payload.get("session_id")
    cfg = _resolve_config(payload.get("config") or {})
    prior_results: list[dict[str, Any]] = payload.get("prior_results") or []

    # --- locate CSV ---
    try:
        csv_path = _locate_training_csv(dataset_id, prior_results)
    except ValueError as exc:
        return _failed(step, str(exc))
    try:
        raise_if_interrupted(session_id, context="Training interrupted by user.")
    except UserInterruptRequested as exc:
        return _failed(step, str(exc))

    # --- load schema (needed for target inference) ---
    schema_profile = get_upload_schema_by_file_id(dataset_id)
    if schema_profile is None:
        return _failed(step, f"Schema profile not found for dataset '{dataset_id}'.")

    # --- read CSV ---
    try:
        df = _read_csv(str(csv_path))
    except Exception as exc:
        return _failed(step, f"Could not read CSV: {exc}\n{traceback.format_exc()}")

    if df.empty:
        return _failed(step, "CSV file contains no data rows.")
    await _publish_progress(
        session_id,
        step=step,
        percent=10,
        message=f"Loaded training data with {len(df)} rows and {len(df.columns)} columns.",
    )

    # --- resolve target column ---
    target_column: str | None = cfg.get("target_column")
    target_inferred = False
    if not target_column:
        try:
            target_column = _infer_target_column(df, schema_profile)
            target_inferred = True
        except ValueError as exc:
            return _failed(step, str(exc))

    if target_column not in df.columns:
        return _failed(
            step,
            f"Target column '{target_column}' not found in dataset. "
            f"Available columns: {sorted(df.columns.tolist())}",
        )
    try:
        raise_if_interrupted(session_id, context="Training interrupted by user.")
    except UserInterruptRequested as exc:
        return _failed(step, str(exc))
    await _publish_progress(
        session_id,
        step=step,
        percent=20,
        message=f"Using target column '{target_column}' ({'inferred' if target_inferred else 'configured'}).",
    )

    # --- split features and target ---
    X, y = _split_features_target(df, target_column)

    if X.empty:
        return _failed(step, "No feature columns remain after separating the target column.")

    if y.isnull().all():
        return _failed(step, f"Target column '{target_column}' contains only null values.")

    n_samples, n_features = X.shape

    # --- detect task type and metric ---
    task_type: str = _detect_task_type(y, cfg.get("task_type"))
    metric: str = cfg.get("metric") or _pick_metric(task_type, y)
    await _publish_progress(
        session_id,
        step=step,
        percent=30,
        message=f"Prepared feature matrix with {n_samples} rows, {n_features} features; task={task_type}.",
    )

    # --- select candidates ---
    model_override: str | None = cfg.get("model")
    candidates: list[str] = [model_override] if model_override else _select_candidate_models(
        task_type, n_samples, n_features
    )
    await _publish_progress(
        session_id,
        step=step,
        percent=40,
        message=f"Selected {len(candidates)} training candidate(s): {', '.join(candidates)}.",
    )

    # --- build CV ---
    try:
        cv_folds = _resolve_cv_folds(task_type, y, int(cfg.get("cv_folds") or 5))
    except ValueError as exc:
        return _failed(step, str(exc))
    cv = _build_cv(task_type, cv_folds)

    # --- HPO budget ---
    random_state = int(cfg.get("random_state") or 42)
    n_trials_cfg = cfg.get("n_trials")
    n_trials = int(n_trials_cfg) if n_trials_cfg else _scale_n_trials(n_samples)
    timeout = cfg.get("hpo_timeout_seconds")
    if timeout is not None:
        timeout = float(timeout)

    # --- run HPO per candidate ---
    start_time = time.time()
    candidates_evaluated: list[dict[str, Any]] = []
    best_model_name: str | None = None
    best_params: dict[str, Any] = {}
    best_score = float("-inf")

    total_candidates = max(len(candidates), 1)
    for index, model_name in enumerate(candidates, start=1):
        base_percent = 45 + round(((index - 1) / total_candidates) * 30)
        await _publish_progress(
            session_id,
            step=step,
            percent=base_percent,
            message=f"Running hyperparameter search for {model_name} ({index}/{total_candidates}).",
        )
        try:
            params, score = _run_hpo(X, y, model_name, metric, n_trials, cv, random_state, session_id, timeout)
            candidates_evaluated.append({
                "model": model_name,
                "cv_score": round(score, 6),
                "n_trials": n_trials,
            })
            if score > best_score:
                best_score = score
                best_model_name = model_name
                best_params = params
        except UserInterruptRequested as exc:
            return _failed(step, str(exc))
        except Exception as exc:
            candidates_evaluated.append({
                "model": model_name,
                "cv_score": None,
                "n_trials": n_trials,
                "error": str(exc),
            })
        complete_percent = 45 + round((index / total_candidates) * 30)
        latest = candidates_evaluated[-1]
        latest_score = latest.get("cv_score")
        await _publish_progress(
            session_id,
            step=step,
            percent=complete_percent,
            message=(
                f"Finished candidate {model_name} ({index}/{total_candidates})"
                + (f" with score {latest_score}." if latest_score is not None else ".")
            ),
        )

    if best_model_name is None:
        return _failed(
            step,
            f"All candidate models failed during HPO. Details: {candidates_evaluated}",
        )
    await _publish_progress(
        session_id,
        step=step,
        percent=80,
        message=f"Best candidate selected: {best_model_name}. Training final model.",
    )

    # --- train final model on full data ---
    try:
        final_model = _fit_final_model(X, y, best_model_name, best_params, random_state)
    except Exception as exc:
        return _failed(step, f"Final model training failed: {exc}\n{traceback.format_exc()}")
    try:
        raise_if_interrupted(session_id, context="Training interrupted by user.")
    except UserInterruptRequested as exc:
        return _failed(step, str(exc))
    await _publish_progress(
        session_id,
        step=step,
        percent=92,
        message=f"Final {best_model_name} model trained. Saving artifacts.",
    )

    training_time = round(time.time() - start_time, 2)

    # --- persist model ---
    model_file_id = f"model_{dataset_id}"
    if not model_file_id.endswith(".joblib"):
        model_file_id += ".joblib"
    out_path = UPLOAD_DIR / model_file_id
    try:
        _save_model(final_model, out_path)
    except Exception as exc:
        return _failed(step, f"Failed to save model to disk: {exc}")

    result_data: dict[str, Any] = {
        "task_type": task_type,
        "target_column": target_column,
        "target_inferred": target_inferred,
        "n_samples": n_samples,
        "n_features": n_features,
        "metric": metric,
        "cv_folds": cv_folds,
        "chosen_model": best_model_name,
        "best_params": best_params,
        "cv_score": round(best_score, 6),
        "candidates_evaluated": candidates_evaluated,
        "model_file_id": model_file_id,
        "training_time_seconds": training_time,
    }
    report_file_id = safe_artifact_file_id("training_report", dataset_id, ".json")
    report_path = write_json_artifact(report_file_id, result_data)

    return {
        "status": "success",
        "result": result_data,
        "artifacts": [
            {
                "name": "trained_model.joblib",
                "type": "joblib",
                "path": str(out_path),
                "file_id": model_file_id,
            },
            {
                "name": "training_report.json",
                "type": "json",
                "path": str(report_path),
                "file_id": report_file_id,
            },
        ],
        "dashboard_updates": [
            {
                "agent": "model_training_agent",
                "step": step,
                "status": "completed",
                "message": (
                    f"Trained {best_model_name} — {metric}={best_score:.4f} "
                    f"on {n_samples} rows "
                    f"({len(candidates_evaluated)} candidate(s) in {training_time}s)"
                ),
            }
        ],
    }


# ---------------------------------------------------------------------------
# Failure helper
# ---------------------------------------------------------------------------

def _failed(step: str, message: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "result": {"error": message},
        "artifacts": [],
        "dashboard_updates": [
            {
                "agent": "model_training_agent",
                "step": step,
                "status": "failed",
                "message": message,
            }
        ],
    }
