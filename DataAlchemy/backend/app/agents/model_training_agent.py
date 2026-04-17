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
from app.db.models import get_upload_schema_by_file_id, get_upload_stored_path_by_file_id
from app.engine.registry import get_agent_config

optuna.logging.set_verbosity(optuna.logging.WARNING)

# ---------------------------------------------------------------------------
# Known target-column names (ordered by priority)
# ---------------------------------------------------------------------------

_TARGET_NAMES: frozenset[str] = frozenset({
    "target", "label", "y", "class", "churn", "exited",
    "fraud", "price", "outcome", "survived", "default",
})


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

    # 3. DB stored path 
    stored_path = get_upload_stored_path_by_file_id(dataset_id)
    if stored_path and Path(stored_path).exists():
        return Path(stored_path)

    # 4. Direct fallback (UPLOAD_DIR/dataset_id)
    alt = UPLOAD_DIR / dataset_id
    if alt.exists():
        return alt

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

def _infer_target_column(df: pd.DataFrame, schema_profile: dict[str, Any]) -> str:
    """Infer the most likely target column from the schema profile.

    Priority:
      1. Column name matches a known target-name keyword
      2. Binary integer column (unique_count == 2)
      3. Low-cardinality integer/categorical column (2 <= unique_count <= 10)
    """
    df_cols: set[str] = set(df.columns)
    columns: list[dict[str, Any]] = schema_profile.get("columns", [])

    # 1. Named match (check DataFrame columns directly first, then schema)
    for name in _TARGET_NAMES:
        if name in df_cols:
            return name

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
    if n_samples < 1_000:
        return 50
    if n_samples < 10_000:
        return 30
    if n_samples < 100_000:
        return 15
    return 10


# ---------------------------------------------------------------------------
# CV builder
# ---------------------------------------------------------------------------

def _build_cv(task_type: str, n_splits: int = 5):
    if task_type == "classification":
        return StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    return KFold(n_splits=n_splits, shuffle=True, random_state=42)


# ---------------------------------------------------------------------------
# Optuna search spaces
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
    timeout: float | None = None,
) -> tuple[dict[str, Any], float]:
    """Run Optuna HPO for one candidate model; return (best_params, best_cv_score)."""

    def objective(trial: optuna.Trial) -> float:
        params = _get_search_space(trial, model_name)
        model = _build_model(model_name, params, random_state)
        scores = cross_val_score(model, X, y, cv=cv, scoring=metric, error_score=0.0)
        return float(scores.mean())

    pruner = optuna.pruners.MedianPruner(n_startup_trials=5)
    sampler = optuna.samplers.TPESampler(seed=random_state)
    study = optuna.create_study(direction="maximize", pruner=pruner, sampler=sampler)
    study.optimize(objective, n_trials=n_trials, timeout=timeout, show_progress_bar=False)

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
    cfg = _resolve_config(payload.get("config") or {})
    prior_results: list[dict[str, Any]] = payload.get("prior_results") or []

    # --- locate CSV ---
    try:
        csv_path = _locate_training_csv(dataset_id, prior_results)
    except ValueError as exc:
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

    # --- split features and target ---
    X, y = _split_features_target(df, target_column)

    if X.empty:
        return _failed(step, "No feature columns remain after separating the target column.")

    if y.isnull().all():
        return _failed(step, f"Target column '{target_column}' contains only null values.")

    n_samples, n_features = X.shape

    if n_samples < 10:
        return _failed(step, f"Too few rows ({n_samples}) to train a model reliably.")

    # --- detect task type and metric ---
    task_type: str = _detect_task_type(y, cfg.get("task_type"))
    metric: str = cfg.get("metric") or _pick_metric(task_type, y)

    # --- select candidates ---
    model_override: str | None = cfg.get("model")
    candidates: list[str] = [model_override] if model_override else _select_candidate_models(
        task_type, n_samples, n_features
    )

    # --- build CV ---
    cv_folds = max(2, int(cfg.get("cv_folds") or 5))
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

    for model_name in candidates:
        try:
            params, score = _run_hpo(X, y, model_name, metric, n_trials, cv, random_state, timeout)
            candidates_evaluated.append({
                "model": model_name,
                "cv_score": round(score, 6),
                "n_trials": n_trials,
            })
            if score > best_score:
                best_score = score
                best_model_name = model_name
                best_params = params
        except Exception as exc:
            candidates_evaluated.append({
                "model": model_name,
                "cv_score": None,
                "n_trials": n_trials,
                "error": str(exc),
            })

    if best_model_name is None:
        return _failed(
            step,
            f"All candidate models failed during HPO. Details: {candidates_evaluated}",
        )

    # --- train final model on full data ---
    try:
        final_model = _fit_final_model(X, y, best_model_name, best_params, random_state)
    except Exception as exc:
        return _failed(step, f"Final model training failed: {exc}\n{traceback.format_exc()}")

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
        "chosen_model": best_model_name,
        "best_params": best_params,
        "cv_score": round(best_score, 6),
        "candidates_evaluated": candidates_evaluated,
        "model_file_id": model_file_id,
        "training_time_seconds": training_time,
    }

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
                "data": result_data,
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
