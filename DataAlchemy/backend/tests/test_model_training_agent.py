"""Unit and integration tests for the model_training_agent module."""

from __future__ import annotations

import csv
import io
import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def clf_csv(tmp_path: Path) -> Path:
    """Small binary-classification CSV: 150 rows, 4 numeric features, binary target."""
    rng = np.random.default_rng(0)
    n = 150
    rows = [
        {
            "f1": round(float(rng.normal(0, 1)), 4),
            "f2": round(float(rng.normal(0, 1)), 4),
            "f3": round(float(rng.uniform(0, 10)), 4),
            "f4": round(float(rng.uniform(0, 10)), 4),
            "target": int(rng.integers(0, 2)),
        }
        for _ in range(n)
    ]
    path = tmp_path / "clf.csv"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["f1", "f2", "f3", "f4", "target"])
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def reg_csv(tmp_path: Path) -> Path:
    """Small regression CSV: 200 rows, 3 numeric features, continuous target."""
    rng = np.random.default_rng(1)
    n = 200
    rows = [
        {
            "x1": round(float(rng.normal(0, 1)), 4),
            "x2": round(float(rng.normal(5, 2)), 4),
            "x3": round(float(rng.uniform(0, 10)), 4),
            "price": round(float(rng.normal(100, 20)), 4),
        }
        for _ in range(n)
    ]
    path = tmp_path / "reg.csv"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["x1", "x2", "x3", "price"])
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def clf_schema() -> dict[str, Any]:
    return {
        "rows_sampled": 150,
        "columns": [
            {"name": "f1", "inferred_dtype": "float", "unique_count": 150, "non_null_count": 150, "null_ratio": 0.0},
            {"name": "f2", "inferred_dtype": "float", "unique_count": 150, "non_null_count": 150, "null_ratio": 0.0},
            {"name": "f3", "inferred_dtype": "float", "unique_count": 150, "non_null_count": 150, "null_ratio": 0.0},
            {"name": "f4", "inferred_dtype": "float", "unique_count": 150, "non_null_count": 150, "null_ratio": 0.0},
            {"name": "target", "inferred_dtype": "integer", "unique_count": 2, "non_null_count": 150, "null_ratio": 0.0},
        ],
    }


@pytest.fixture
def reg_schema() -> dict[str, Any]:
    return {
        "rows_sampled": 200,
        "columns": [
            {"name": "x1", "inferred_dtype": "float", "unique_count": 200, "non_null_count": 200, "null_ratio": 0.0},
            {"name": "x2", "inferred_dtype": "float", "unique_count": 200, "non_null_count": 200, "null_ratio": 0.0},
            {"name": "x3", "inferred_dtype": "float", "unique_count": 200, "non_null_count": 200, "null_ratio": 0.0},
            {"name": "price", "inferred_dtype": "float", "unique_count": 200, "non_null_count": 200, "null_ratio": 0.0},
        ],
    }


@pytest.fixture
def tiny_iris_csv(tmp_path: Path) -> Path:
    path = tmp_path / "preprocessed_tiny_iris.csv"
    path.write_text(
        "\n".join(
            [
                "sepal_length,sepal_width,petal_length,petal_width,species",
                "5.1,3.5,1.4,0.2,setosa",
                "4.9,3.0,1.4,0.2,setosa",
                "6.2,3.4,5.4,2.3,virginica",
                "5.9,3.0,5.1,1.8,virginica",
                "6.0,2.2,4.0,1.0,versicolor",
                "5.5,2.3,4.0,1.3,versicolor",
            ]
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def tiny_iris_schema() -> dict[str, Any]:
    return {
        "rows_sampled": 6,
        "columns": [
            {"name": "sepal_length", "inferred_dtype": "float", "unique_count": 6, "non_null_count": 6, "null_ratio": 0.0},
            {"name": "sepal_width", "inferred_dtype": "float", "unique_count": 5, "non_null_count": 6, "null_ratio": 0.0},
            {"name": "petal_length", "inferred_dtype": "float", "unique_count": 4, "non_null_count": 6, "null_ratio": 0.0},
            {"name": "petal_width", "inferred_dtype": "float", "unique_count": 6, "non_null_count": 6, "null_ratio": 0.0},
            {"name": "species", "inferred_dtype": "string", "unique_count": 3, "non_null_count": 6, "null_ratio": 0.0},
        ],
    }


# ---------------------------------------------------------------------------
# _infer_target_column
# ---------------------------------------------------------------------------

class TestTargetInference:
    def _df(self, cols: list[str]) -> pd.DataFrame:
        return pd.DataFrame({c: [1, 2, 3] for c in cols})

    def test_named_column_hit(self):
        from app.agents.model_training_agent import _infer_target_column
        df = self._df(["f1", "f2", "target"])
        schema = {"columns": [
            {"name": "f1", "inferred_dtype": "float", "unique_count": 3, "non_null_count": 3},
            {"name": "f2", "inferred_dtype": "float", "unique_count": 3, "non_null_count": 3},
            {"name": "target", "inferred_dtype": "integer", "unique_count": 3, "non_null_count": 3},
        ]}
        assert _infer_target_column(df, schema) == "target"

    def test_binary_integer_column(self):
        from app.agents.model_training_agent import _infer_target_column
        df = self._df(["f1", "label_col"])
        schema = {"columns": [
            {"name": "f1", "inferred_dtype": "float", "unique_count": 3, "non_null_count": 3},
            {"name": "label_col", "inferred_dtype": "integer", "unique_count": 2, "non_null_count": 3},
        ]}
        assert _infer_target_column(df, schema) == "label_col"

    def test_low_cardinality_categorical(self):
        from app.agents.model_training_agent import _infer_target_column
        df = self._df(["f1", "status"])
        schema = {"columns": [
            {"name": "f1", "inferred_dtype": "float", "unique_count": 3, "non_null_count": 3},
            {"name": "status", "inferred_dtype": "categorical", "unique_count": 3, "non_null_count": 3},
        ]}
        assert _infer_target_column(df, schema) == "status"

    def test_no_candidate_raises(self):
        from app.agents.model_training_agent import _infer_target_column
        df = self._df(["f1", "f2"])
        schema = {"columns": [
            {"name": "f1", "inferred_dtype": "float", "unique_count": 3, "non_null_count": 3},
            {"name": "f2", "inferred_dtype": "float", "unique_count": 3, "non_null_count": 3},
        ]}
        with pytest.raises(ValueError, match="Cannot infer target column"):
            _infer_target_column(df, schema)


# ---------------------------------------------------------------------------
# _detect_task_type
# ---------------------------------------------------------------------------

class TestTaskTypeDetection:
    def test_explicit_classification_override(self):
        from app.agents.model_training_agent import _detect_task_type
        y = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0] * 20)
        assert _detect_task_type(y, "classification") == "classification"

    def test_explicit_regression_override(self):
        from app.agents.model_training_agent import _detect_task_type
        y = pd.Series([1, 0, 1, 0])
        assert _detect_task_type(y, "regression") == "regression"

    def test_binary_integer_is_classification(self):
        from app.agents.model_training_agent import _detect_task_type
        y = pd.Series([0, 1, 0, 1, 1, 0])
        assert _detect_task_type(y, None) == "classification"

    def test_string_labels_is_classification(self):
        from app.agents.model_training_agent import _detect_task_type
        y = pd.Series(["cat", "dog", "cat", "dog"])
        assert _detect_task_type(y, None) == "classification"

    def test_continuous_float_is_regression(self):
        from app.agents.model_training_agent import _detect_task_type
        rng = np.random.default_rng(0)
        y = pd.Series(rng.normal(100, 20, size=100))
        assert _detect_task_type(y, None) == "regression"

    def test_high_cardinality_integer_is_regression(self):
        from app.agents.model_training_agent import _detect_task_type
        y = pd.Series(list(range(50)))  # 50 unique integer values
        assert _detect_task_type(y, None) == "regression"


# ---------------------------------------------------------------------------
# _select_candidate_models
# ---------------------------------------------------------------------------

class TestModelSelection:
    def test_small_classification(self):
        from app.agents.model_training_agent import _select_candidate_models
        candidates = _select_candidate_models("classification", 500, 10)
        assert "LogisticRegression" in candidates
        assert "RandomForestClassifier" in candidates
        assert "XGBClassifier" not in candidates

    def test_medium_classification(self):
        from app.agents.model_training_agent import _select_candidate_models
        candidates = _select_candidate_models("classification", 5_000, 10)
        assert "RandomForestClassifier" in candidates
        assert "LGBMClassifier" in candidates

    def test_large_classification(self):
        from app.agents.model_training_agent import _select_candidate_models
        candidates = _select_candidate_models("classification", 50_000, 10)
        assert "LGBMClassifier" in candidates
        assert "XGBClassifier" in candidates
        assert "LogisticRegression" not in candidates

    def test_small_regression(self):
        from app.agents.model_training_agent import _select_candidate_models
        candidates = _select_candidate_models("regression", 999, 5)
        assert "Ridge" in candidates
        assert "RandomForestRegressor" in candidates

    def test_medium_regression(self):
        from app.agents.model_training_agent import _select_candidate_models
        candidates = _select_candidate_models("regression", 9_999, 5)
        assert "RandomForestRegressor" in candidates
        assert "LGBMRegressor" in candidates

    def test_large_regression(self):
        from app.agents.model_training_agent import _select_candidate_models
        candidates = _select_candidate_models("regression", 100_000, 5)
        assert "LGBMRegressor" in candidates
        assert "XGBRegressor" in candidates
        assert "Ridge" not in candidates

    def test_boundary_exactly_1000_is_medium(self):
        from app.agents.model_training_agent import _select_candidate_models
        candidates = _select_candidate_models("classification", 1_000, 10)
        assert "LGBMClassifier" in candidates

    def test_boundary_exactly_10000_is_large(self):
        from app.agents.model_training_agent import _select_candidate_models
        candidates = _select_candidate_models("classification", 10_000, 10)
        assert "XGBClassifier" in candidates


# ---------------------------------------------------------------------------
# _pick_metric
# ---------------------------------------------------------------------------

class TestMetricSelection:
    def test_binary_classification_uses_roc_auc(self):
        from app.agents.model_training_agent import _pick_metric
        y = pd.Series([0, 1, 0, 1, 1])
        assert _pick_metric("classification", y) == "roc_auc"

    def test_multiclass_uses_f1_macro(self):
        from app.agents.model_training_agent import _pick_metric
        y = pd.Series([0, 1, 2, 0, 1, 2])
        assert _pick_metric("classification", y) == "f1_macro"

    def test_regression_uses_neg_rmse(self):
        from app.agents.model_training_agent import _pick_metric
        y = pd.Series([1.5, 2.3, 3.1, 4.0])
        assert _pick_metric("regression", y) == "neg_root_mean_squared_error"


# ---------------------------------------------------------------------------
# _scale_n_trials
# ---------------------------------------------------------------------------

class TestScaleNTrials:
    def test_small_dataset_gets_50(self):
        from app.agents.model_training_agent import _scale_n_trials
        assert _scale_n_trials(999) == 50

    def test_boundary_1000_gets_30(self):
        from app.agents.model_training_agent import _scale_n_trials
        assert _scale_n_trials(1_000) == 30

    def test_medium_gets_30(self):
        from app.agents.model_training_agent import _scale_n_trials
        assert _scale_n_trials(5_000) == 30

    def test_boundary_10000_gets_15(self):
        from app.agents.model_training_agent import _scale_n_trials
        assert _scale_n_trials(10_000) == 15

    def test_large_gets_15(self):
        from app.agents.model_training_agent import _scale_n_trials
        assert _scale_n_trials(50_000) == 15

    def test_boundary_100000_gets_10(self):
        from app.agents.model_training_agent import _scale_n_trials
        assert _scale_n_trials(100_000) == 10

    def test_very_large_gets_10(self):
        from app.agents.model_training_agent import _scale_n_trials
        assert _scale_n_trials(1_000_000) == 10


# ---------------------------------------------------------------------------
# Full handler integration
# ---------------------------------------------------------------------------

class TestModelTrainingHandlerIntegration:

    def _patch_all(self, csv_path: Path, schema: dict, tmp_path: Path):
        """Return a context manager that patches DB helpers and UPLOAD_DIR."""
        return (
            patch(
                "app.agents.model_training_agent.get_upload_stored_path_by_file_id",
                return_value=str(csv_path),
            ),
            patch(
                "app.agents.model_training_agent.get_upload_schema_by_file_id",
                return_value=schema,
            ),
            patch(
                "app.agents.model_training_agent.get_agent_config",
                return_value={"defaults": {}},
            ),
            patch("app.agents.model_training_agent.UPLOAD_DIR", tmp_path),
        )

    @pytest.mark.asyncio
    async def test_classification_success(
        self, tmp_path: Path, clf_csv: Path, clf_schema: dict
    ):
        from app.agents.model_training_agent import model_training_handler

        payload = {
            "dataset_id": "clf.csv",
            "step": "train_model",
            "agent": "model_training_agent",
            "config": {"target_column": "target", "n_trials": 3, "cv_folds": 2},
            "prior_results": [],
        }

        with (
            patch("app.agents.model_training_agent.get_upload_stored_path_by_file_id", return_value=str(clf_csv)),
            patch("app.agents.model_training_agent.get_upload_schema_by_file_id", return_value=clf_schema),
            patch("app.agents.model_training_agent.get_agent_config", return_value={"defaults": {}}),
            patch("app.agents.model_training_agent.UPLOAD_DIR", tmp_path),
        ):
            result = await model_training_handler(payload)

        assert result["status"] == "success", result.get("result", {}).get("error")
        r = result["result"]
        assert r["task_type"] == "classification"
        assert r["target_column"] == "target"
        assert r["n_samples"] == 150
        assert r["n_features"] == 4
        assert r["cv_score"] > 0
        assert r["chosen_model"] in {
            "LogisticRegression", "RandomForestClassifier",
            "GradientBoostingClassifier", "LGBMClassifier", "XGBClassifier",
        }
        assert len(r["candidates_evaluated"]) >= 1
        assert (tmp_path / r["model_file_id"]).exists()

        artifact_names = [a["name"] for a in result["artifacts"]]
        assert "trained_model.joblib" in artifact_names
        assert "training_report.json" in artifact_names
        assert len(result["dashboard_updates"]) == 1

    @pytest.mark.asyncio
    async def test_regression_success(
        self, tmp_path: Path, reg_csv: Path, reg_schema: dict
    ):
        from app.agents.model_training_agent import model_training_handler

        payload = {
            "dataset_id": "reg.csv",
            "step": "train_model",
            "agent": "model_training_agent",
            "config": {"target_column": "price", "n_trials": 3, "cv_folds": 2},
            "prior_results": [],
        }

        with (
            patch("app.agents.model_training_agent.get_upload_stored_path_by_file_id", return_value=str(reg_csv)),
            patch("app.agents.model_training_agent.get_upload_schema_by_file_id", return_value=reg_schema),
            patch("app.agents.model_training_agent.get_agent_config", return_value={"defaults": {}}),
            patch("app.agents.model_training_agent.UPLOAD_DIR", tmp_path),
        ):
            result = await model_training_handler(payload)

        assert result["status"] == "success", result.get("result", {}).get("error")
        r = result["result"]
        assert r["task_type"] == "regression"
        assert r["metric"] == "neg_root_mean_squared_error"

    @pytest.mark.asyncio
    async def test_target_inferred_when_not_in_config(
        self, tmp_path: Path, clf_csv: Path, clf_schema: dict
    ):
        from app.agents.model_training_agent import model_training_handler

        payload = {
            "dataset_id": "clf.csv",
            "step": "train_model",
            "agent": "model_training_agent",
            "config": {"n_trials": 3, "cv_folds": 2},  # no target_column
            "prior_results": [],
        }

        with (
            patch("app.agents.model_training_agent.get_upload_stored_path_by_file_id", return_value=str(clf_csv)),
            patch("app.agents.model_training_agent.get_upload_schema_by_file_id", return_value=clf_schema),
            patch("app.agents.model_training_agent.get_agent_config", return_value={"defaults": {}}),
            patch("app.agents.model_training_agent.UPLOAD_DIR", tmp_path),
        ):
            result = await model_training_handler(payload)

        assert result["status"] == "success"
        assert result["result"]["target_inferred"] is True
        assert result["result"]["target_column"] == "target"

    @pytest.mark.asyncio
    async def test_reads_preprocessed_file_from_prior_results(
        self, tmp_path: Path, clf_csv: Path, clf_schema: dict
    ):
        """When prior_results contains a preprocessing step, the agent should use its file."""
        from app.agents.model_training_agent import model_training_handler

        # Copy clf_csv into tmp_path so the agent can find it as a preprocessed file
        import shutil
        preprocessed_path = tmp_path / "preprocessed_clf.csv"
        shutil.copy(clf_csv, preprocessed_path)

        prior_results = [
            {
                "agent": "data_preprocessing_agent",
                "step": "preprocess_data",
                "result": {"preprocessed_file_id": "preprocessed_clf.csv"},
            }
        ]

        payload = {
            "dataset_id": "clf.csv",
            "step": "train_model",
            "agent": "model_training_agent",
            "config": {"target_column": "target", "n_trials": 3, "cv_folds": 2},
            "prior_results": prior_results,
        }

        with (
            patch("app.agents.model_training_agent.get_upload_stored_path_by_file_id", return_value=str(clf_csv)),
            patch("app.agents.model_training_agent.get_upload_schema_by_file_id", return_value=clf_schema),
            patch("app.agents.model_training_agent.get_agent_config", return_value={"defaults": {}}),
            patch("app.agents.model_training_agent.UPLOAD_DIR", tmp_path),
        ):
            result = await model_training_handler(payload)

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_model_override_in_config(
        self, tmp_path: Path, clf_csv: Path, clf_schema: dict
    ):
        """When config.model is set, only that model should be evaluated."""
        from app.agents.model_training_agent import model_training_handler

        payload = {
            "dataset_id": "clf.csv",
            "step": "train_model",
            "agent": "model_training_agent",
            "config": {
                "target_column": "target",
                "model": "LogisticRegression",
                "n_trials": 3,
                "cv_folds": 2,
            },
            "prior_results": [],
        }

        with (
            patch("app.agents.model_training_agent.get_upload_stored_path_by_file_id", return_value=str(clf_csv)),
            patch("app.agents.model_training_agent.get_upload_schema_by_file_id", return_value=clf_schema),
            patch("app.agents.model_training_agent.get_agent_config", return_value={"defaults": {}}),
            patch("app.agents.model_training_agent.UPLOAD_DIR", tmp_path),
        ):
            result = await model_training_handler(payload)

        assert result["status"] == "success"
        assert result["result"]["chosen_model"] == "LogisticRegression"
        assert len(result["result"]["candidates_evaluated"]) == 1

    @pytest.mark.asyncio
    async def test_saved_model_is_loadable(
        self, tmp_path: Path, clf_csv: Path, clf_schema: dict
    ):
        """Verify the saved joblib file is a fitted estimator that can predict."""
        import joblib
        from app.agents.model_training_agent import model_training_handler

        payload = {
            "dataset_id": "clf.csv",
            "step": "train_model",
            "agent": "model_training_agent",
            "config": {
                "target_column": "target",
                "model": "LogisticRegression",
                "n_trials": 2,
                "cv_folds": 2,
            },
            "prior_results": [],
        }

        with (
            patch("app.agents.model_training_agent.get_upload_stored_path_by_file_id", return_value=str(clf_csv)),
            patch("app.agents.model_training_agent.get_upload_schema_by_file_id", return_value=clf_schema),
            patch("app.agents.model_training_agent.get_agent_config", return_value={"defaults": {}}),
            patch("app.agents.model_training_agent.UPLOAD_DIR", tmp_path),
        ):
            result = await model_training_handler(payload)

        assert result["status"] == "success"
        model_path = tmp_path / result["result"]["model_file_id"]
        loaded = joblib.load(model_path)
        preds = loaded.predict(pd.DataFrame({"f1": [0.1], "f2": [0.2], "f3": [0.3], "f4": [0.4]}))
        assert preds[0] in {0, 1}

    def test_tiny_multiclass_dataset_caps_cv_folds(
        self, tmp_path: Path, tiny_iris_csv: Path, tiny_iris_schema: dict
    ):
        from app.agents.model_training_agent import model_training_handler

        payload = {
            "dataset_id": "tiny_iris.csv",
            "step": "train_classification_model",
            "agent": "model_training_agent",
            "config": {"n_trials": 1},
            "prior_results": [
                {
                    "agent": "data_preprocessing_agent",
                    "result": {"preprocessed_file_id": tiny_iris_csv.name},
                }
            ],
        }

        with (
            patch("app.agents.model_training_agent.get_upload_schema_by_file_id", return_value=tiny_iris_schema),
            patch("app.agents.model_training_agent.get_agent_config", return_value={"defaults": {}}),
            patch("app.agents.model_training_agent.UPLOAD_DIR", tmp_path),
        ):
            result = asyncio.run(model_training_handler(payload))

        assert result["status"] == "success", result.get("result", {}).get("error")
        assert result["result"]["target_column"] == "species"
        assert result["result"]["task_type"] == "classification"
        assert result["result"]["cv_folds"] == 2
        assert result["result"]["n_samples"] == 6

    @pytest.mark.asyncio
    async def test_fails_when_dataset_not_found(self, tmp_path: Path, clf_schema: dict):
        from app.agents.model_training_agent import model_training_handler

        payload = {
            "dataset_id": "ghost.csv",
            "step": "train_model",
            "agent": "model_training_agent",
            "config": {"target_column": "target", "n_trials": 2},
            "prior_results": [],
        }

        with (
            patch("app.agents.model_training_agent.get_upload_stored_path_by_file_id", return_value=None),
            patch("app.agents.model_training_agent.get_upload_schema_by_file_id", return_value=clf_schema),
            patch("app.agents.model_training_agent.get_agent_config", return_value={"defaults": {}}),
            patch("app.agents.model_training_agent.UPLOAD_DIR", tmp_path),
        ):
            result = await model_training_handler(payload)

        assert result["status"] == "failed"
        assert "Cannot locate" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_fails_when_schema_missing(self, tmp_path: Path, clf_csv: Path):
        from app.agents.model_training_agent import model_training_handler

        payload = {
            "dataset_id": "clf.csv",
            "step": "train_model",
            "agent": "model_training_agent",
            "config": {"target_column": "target", "n_trials": 2},
            "prior_results": [],
        }

        with (
            patch("app.agents.model_training_agent.get_upload_stored_path_by_file_id", return_value=str(clf_csv)),
            patch("app.agents.model_training_agent.get_upload_schema_by_file_id", return_value=None),
            patch("app.agents.model_training_agent.get_agent_config", return_value={"defaults": {}}),
            patch("app.agents.model_training_agent.UPLOAD_DIR", tmp_path),
        ):
            result = await model_training_handler(payload)

        assert result["status"] == "failed"
        assert "Schema profile not found" in result["result"]["error"]

    @pytest.mark.asyncio
    async def test_fails_when_target_column_not_in_data(
        self, tmp_path: Path, clf_csv: Path, clf_schema: dict
    ):
        from app.agents.model_training_agent import model_training_handler

        payload = {
            "dataset_id": "clf.csv",
            "step": "train_model",
            "agent": "model_training_agent",
            "config": {"target_column": "nonexistent_col", "n_trials": 2},
            "prior_results": [],
        }

        with (
            patch("app.agents.model_training_agent.get_upload_stored_path_by_file_id", return_value=str(clf_csv)),
            patch("app.agents.model_training_agent.get_upload_schema_by_file_id", return_value=clf_schema),
            patch("app.agents.model_training_agent.get_agent_config", return_value={"defaults": {}}),
            patch("app.agents.model_training_agent.UPLOAD_DIR", tmp_path),
        ):
            result = await model_training_handler(payload)

        assert result["status"] == "failed"
        assert "nonexistent_col" in result["result"]["error"]
