"""Unit tests for the data_preprocessing_agent module."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rows(data: dict[str, list[Any]]) -> tuple[list[str], list[dict[str, str]]]:
    """Build (fieldnames, rows) from a column-oriented dict."""
    fieldnames = list(data.keys())
    n = len(next(iter(data.values())))
    rows = [{col: str(data[col][i]) for col in fieldnames} for i in range(n)]
    return fieldnames, rows


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------

class TestDeduplicate:
    def test_no_duplicates_unchanged(self):
        from app.agents.data_preprocessing_agent import deduplicate
        rows = [{"a": "1"}, {"a": "2"}, {"a": "3"}]
        out, removed = deduplicate(rows, ["a"])
        assert removed == 0
        assert len(out) == 3

    def test_removes_exact_duplicates(self):
        from app.agents.data_preprocessing_agent import deduplicate
        rows = [{"a": "1"}, {"a": "1"}, {"a": "2"}]
        out, removed = deduplicate(rows, ["a"])
        assert removed == 1
        assert len(out) == 2

    def test_partial_match_not_duplicate(self):
        from app.agents.data_preprocessing_agent import deduplicate
        rows = [{"a": "1", "b": "X"}, {"a": "1", "b": "Y"}]
        out, removed = deduplicate(rows, ["a", "b"])
        assert removed == 0


# ---------------------------------------------------------------------------
# drop_columns
# ---------------------------------------------------------------------------

class TestDropColumns:
    def _profile(self, cols: list[tuple[str, str, int]]) -> dict[str, Any]:
        return {"columns": [{"name": n, "inferred_dtype": d, "unique_count": u} for n, d, u in cols]}

    def test_explicit_drop(self):
        from app.agents.data_preprocessing_agent import drop_columns
        rows = [{"a": "1", "b": "2"}]
        profile = self._profile([("a", "integer", 1), ("b", "integer", 1)])
        _, new_fn, dropped = drop_columns(rows, ["a", "b"], profile, ["b"], False, 1)
        assert "b" not in new_fn
        assert "a" in new_fn
        assert "b" in dropped

    def test_auto_drop_id_column(self):
        from app.agents.data_preprocessing_agent import drop_columns
        rows = [{"id": str(i), "val": "x"} for i in range(5)]
        profile = self._profile([("id", "string", 5), ("val", "categorical", 1)])
        _, new_fn, dropped = drop_columns(rows, ["id", "val"], profile, [], True, 5)
        assert "id" in dropped
        assert "val" not in dropped

    def test_auto_drop_disabled(self):
        from app.agents.data_preprocessing_agent import drop_columns
        rows = [{"id": str(i)} for i in range(5)]
        profile = self._profile([("id", "string", 5)])
        _, new_fn, dropped = drop_columns(rows, ["id"], profile, [], False, 5)
        assert "id" not in dropped


# ---------------------------------------------------------------------------
# impute_missing
# ---------------------------------------------------------------------------

class TestImputeMissing:
    def _profile_numeric(self, col: str) -> dict[str, Any]:
        return {"columns": [{"name": col, "inferred_dtype": "float"}]}

    def _profile_categorical(self, col: str) -> dict[str, Any]:
        return {"columns": [{"name": col, "inferred_dtype": "categorical"}]}

    def test_mean_imputation(self):
        from app.agents.data_preprocessing_agent import impute_missing
        rows = [{"x": "10"}, {"x": ""}, {"x": "20"}]
        new_rows, log = impute_missing(rows, ["x"], self._profile_numeric("x"), "mean", "mode")
        assert float(new_rows[1]["x"]) == pytest.approx(15.0)
        assert len(log) == 1

    def test_median_imputation(self):
        from app.agents.data_preprocessing_agent import impute_missing
        rows = [{"x": "10"}, {"x": "NA"}, {"x": "20"}, {"x": "30"}]
        new_rows, log = impute_missing(rows, ["x"], self._profile_numeric("x"), "median", "mode")
        assert float(new_rows[1]["x"]) == pytest.approx(20.0)

    def test_constant_imputation_numeric(self):
        from app.agents.data_preprocessing_agent import impute_missing
        rows = [{"x": "5"}, {"x": "null"}]
        new_rows, _ = impute_missing(rows, ["x"], self._profile_numeric("x"), "constant", "mode")
        assert float(new_rows[1]["x"]) == 0.0

    def test_mode_imputation_categorical(self):
        from app.agents.data_preprocessing_agent import impute_missing
        rows = [{"cat": "A"}, {"cat": "A"}, {"cat": "B"}, {"cat": ""}]
        new_rows, log = impute_missing(rows, ["cat"], self._profile_categorical("cat"), "mean", "mode")
        assert str(new_rows[3]["cat"]) == "A"
        assert len(log) == 1

    def test_no_log_when_no_nulls(self):
        from app.agents.data_preprocessing_agent import impute_missing
        rows = [{"x": "1"}, {"x": "2"}]
        _, log = impute_missing(rows, ["x"], self._profile_numeric("x"), "mean", "mode")
        assert log == []


# ---------------------------------------------------------------------------
# encode_columns
# ---------------------------------------------------------------------------

class TestEncodeColumns:
    def _profile(self, col: str, dtype: str, unique: int) -> dict[str, Any]:
        return {"columns": [{"name": col, "inferred_dtype": dtype, "unique_count": unique}]}

    def test_onehot_encoding(self):
        from app.agents.data_preprocessing_agent import encode_columns
        rows = [{"cat": "A"}, {"cat": "B"}, {"cat": "A"}]
        profile = self._profile("cat", "categorical", 2)
        new_rows, new_fn, log = encode_columns(rows, ["cat"], profile, "onehot", 15, None)
        assert "cat_A" in new_fn
        assert "cat_B" in new_fn
        assert "cat" not in new_fn
        assert new_rows[0]["cat_A"] == 1
        assert new_rows[0]["cat_B"] == 0

    def test_label_encoding(self):
        from app.agents.data_preprocessing_agent import encode_columns
        rows = [{"cat": "X"}, {"cat": "Y"}, {"cat": "X"}]
        profile = self._profile("cat", "categorical", 2)
        new_rows, new_fn, log = encode_columns(rows, ["cat"], profile, "label", 15, None)
        assert "cat" in new_fn
        assert isinstance(new_rows[0]["cat"], int)
        assert new_rows[0]["cat"] == new_rows[2]["cat"]

    def test_falls_back_to_label_when_high_cardinality(self):
        from app.agents.data_preprocessing_agent import encode_columns
        unique_vals = [str(i) for i in range(20)]
        rows = [{"cat": v} for v in unique_vals]
        profile = self._profile("cat", "categorical", 20)
        _, new_fn, log = encode_columns(rows, ["cat"], profile, "onehot", 15, None)
        # 20 > 15, so label encoding fallback
        assert "cat" in new_fn
        assert not any("cat_" in f for f in new_fn)
        assert any("label_encode_fallback" in e["action"] for e in log)

    def test_target_column_not_encoded(self):
        from app.agents.data_preprocessing_agent import encode_columns
        rows = [{"cat": "A", "target": "1"}, {"cat": "B", "target": "0"}]
        profile = {"columns": [
            {"name": "cat", "inferred_dtype": "categorical", "unique_count": 2},
            {"name": "target", "inferred_dtype": "categorical", "unique_count": 2},
        ]}
        _, new_fn, _ = encode_columns(rows, ["cat", "target"], profile, "onehot", 15, "target")
        assert "target" in new_fn
        assert "cat_A" in new_fn

    def test_numeric_columns_not_encoded(self):
        from app.agents.data_preprocessing_agent import encode_columns
        rows = [{"num": "1.5"}, {"num": "2.5"}]
        profile = self._profile("num", "float", 2)
        _, new_fn, log = encode_columns(rows, ["num"], profile, "onehot", 15, None)
        assert "num" in new_fn
        assert log == []


# ---------------------------------------------------------------------------
# scale_columns
# ---------------------------------------------------------------------------

class TestScaleColumns:
    def _profile(self, col: str) -> dict[str, Any]:
        return {"columns": [{"name": col, "inferred_dtype": "float"}]}

    def test_standard_scaling(self):
        from app.agents.data_preprocessing_agent import scale_columns
        rows = [{"x": str(i)} for i in range(1, 6)]
        new_rows, log = scale_columns(rows, ["x"], self._profile("x"), "standard", None)
        scaled = [float(r["x"]) for r in new_rows]
        assert abs(sum(scaled) / len(scaled)) < 1e-6, "Mean should be ~0"
        assert len(log) == 1

    def test_minmax_scaling(self):
        from app.agents.data_preprocessing_agent import scale_columns
        rows = [{"x": str(i)} for i in range(0, 11)]
        new_rows, log = scale_columns(rows, ["x"], self._profile("x"), "minmax", None)
        scaled = [float(r["x"]) for r in new_rows]
        assert min(scaled) == pytest.approx(0.0)
        assert max(scaled) == pytest.approx(1.0)
        assert len(log) == 1

    def test_none_scaler_does_nothing(self):
        from app.agents.data_preprocessing_agent import scale_columns
        rows = [{"x": "5"}, {"x": "10"}]
        new_rows, log = scale_columns(rows, ["x"], self._profile("x"), "none", None)
        assert log == []
        assert new_rows[0]["x"] == "5"

    def test_target_column_not_scaled(self):
        from app.agents.data_preprocessing_agent import scale_columns
        rows = [{"x": "1", "y": "100"}, {"x": "2", "y": "200"}]
        profile = {"columns": [
            {"name": "x", "inferred_dtype": "float"},
            {"name": "y", "inferred_dtype": "float"},
        ]}
        new_rows, log = scale_columns(rows, ["x", "y"], profile, "standard", target_column="y")
        assert new_rows[0]["y"] == "100", "Target column should not be scaled"
        assert any(e["column"] == "x" for e in log)
        assert not any(e["column"] == "y" for e in log)

    def test_constant_column_not_scaled(self):
        from app.agents.data_preprocessing_agent import scale_columns
        rows = [{"x": "5"}] * 5
        new_rows, log = scale_columns(rows, ["x"], self._profile("x"), "standard", None)
        # std == 0, should skip
        assert new_rows[0]["x"] == "5"


# ---------------------------------------------------------------------------
# separate_target
# ---------------------------------------------------------------------------

class TestSeparateTarget:
    def test_no_target(self):
        from app.agents.data_preprocessing_agent import separate_target
        rows = [{"x": "1"}]
        result = separate_target(rows, ["x"], None)
        assert result == {}

    def test_binary_distribution(self):
        from app.agents.data_preprocessing_agent import separate_target
        rows = [{"y": "0"}] * 60 + [{"y": "1"}] * 40
        result = separate_target(rows, ["y"], "y")
        assert result["target_column"] == "y"
        assert result["total_values"] == 100
        dist = result["class_distribution"]
        assert abs(dist["0"] - 0.60) < 0.01
        assert abs(dist["1"] - 0.40) < 0.01

    def test_missing_target_column(self):
        from app.agents.data_preprocessing_agent import separate_target
        rows = [{"x": "1"}]
        result = separate_target(rows, ["x"], "y")
        assert result == {}


# ---------------------------------------------------------------------------
# date_decomposition
# ---------------------------------------------------------------------------

class TestDateDecomposition:
    def test_iso_date_decomposed(self):
        from app.agents.data_preprocessing_agent import engineer_date_features
        rows = [{"date": "2023-06-15", "val": "1"}, {"date": "2023-01-01", "val": "2"}]
        profile = {"columns": [
            {"name": "date", "inferred_dtype": "string"},
            {"name": "val", "inferred_dtype": "integer"},
        ]}
        new_rows, new_fn, log = engineer_date_features(rows, ["date", "val"], profile)
        assert "date" not in new_fn
        assert "date_year" in new_fn
        assert "date_month" in new_fn
        assert "date_day" in new_fn
        assert "date_dayofweek" in new_fn
        assert new_rows[0]["date_year"] == 2023
        assert new_rows[0]["date_month"] == 6
        assert len(log) == 1

    def test_non_date_string_not_decomposed(self):
        from app.agents.data_preprocessing_agent import engineer_date_features
        rows = [{"name": "Alice"}, {"name": "Bob"}]
        profile = {"columns": [{"name": "name", "inferred_dtype": "string"}]}
        _, new_fn, log = engineer_date_features(rows, ["name"], profile)
        assert "name" in new_fn
        assert log == []

    def test_no_string_columns_no_change(self):
        from app.agents.data_preprocessing_agent import engineer_date_features
        rows = [{"x": "1"}]
        profile = {"columns": [{"name": "x", "inferred_dtype": "integer"}]}
        _, new_fn, log = engineer_date_features(rows, ["x"], profile)
        assert "x" in new_fn
        assert log == []


# ---------------------------------------------------------------------------
# Full handler integration
# ---------------------------------------------------------------------------

class TestDataPreprocessingHandlerIntegration:
    @pytest.mark.asyncio
    async def test_full_handler_success(self, tmp_path: Path, sample_csv: Path, sample_schema_profile: dict):
        from unittest.mock import patch
        from app.agents.data_preprocessing_agent import data_preprocessing_handler

        payload = {
            "dataset_id": "sample.csv",
            "step": "preprocess_data",
            "agent": "data_preprocessing_agent",
            "config": {
                "target_column": "week_4",
                "scaler": "minmax",
                "encoding_strategy": "onehot",
                "auto_drop_ids": True,
            },
        }

        with (
            patch(
                "app.agents.data_preprocessing_agent.get_upload_stored_path_by_file_id",
                return_value=str(sample_csv),
            ),
            patch(
                "app.agents.data_preprocessing_agent.get_upload_schema_by_file_id",
                return_value=sample_schema_profile,
            ),
            patch(
                "app.agents.data_preprocessing_agent.get_agent_config",
                return_value={"defaults": {}},
            ),
            patch("app.agents.data_preprocessing_agent.UPLOAD_DIR", tmp_path),
        ):
            result = await data_preprocessing_handler(payload)

        assert result["status"] == "success"
        r = result["result"]
        assert r["rows_input"] >= r["rows_output"]  # deduplication may have reduced rows
        assert r["columns_output"] >= 1
        assert isinstance(r["transformations_applied"], list)
        assert isinstance(r["preprocessing_log"], list)
        assert "preprocessed_file_id" in r
        # Artifact list
        artifact_names = [a["name"] for a in result["artifacts"]]
        assert "preprocessed_dataset.csv" in artifact_names
        assert "preprocessing_log.json" in artifact_names

    @pytest.mark.asyncio
    async def test_handler_fails_when_dataset_missing(self, tmp_path: Path, sample_schema_profile: dict):
        from unittest.mock import patch
        from app.agents.data_preprocessing_agent import data_preprocessing_handler

        payload = {
            "dataset_id": "ghost.csv",
            "step": "preprocess",
            "agent": "data_preprocessing_agent",
            "config": {},
        }

        with (
            patch(
                "app.agents.data_preprocessing_agent.get_upload_stored_path_by_file_id",
                return_value=None,
            ),
            patch(
                "app.agents.data_preprocessing_agent.get_upload_schema_by_file_id",
                return_value=sample_schema_profile,
            ),
            patch(
                "app.agents.data_preprocessing_agent.get_agent_config",
                return_value={"defaults": {}},
            ),
            patch("app.agents.data_preprocessing_agent.UPLOAD_DIR", tmp_path),
        ):
            result = await data_preprocessing_handler(payload)

        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_handler_label_encoding(self, tmp_path: Path, sample_csv: Path, sample_schema_profile: dict):
        from unittest.mock import patch
        from app.agents.data_preprocessing_agent import data_preprocessing_handler

        payload = {
            "dataset_id": "sample.csv",
            "step": "preprocess_data",
            "agent": "data_preprocessing_agent",
            "config": {
                "encoding_strategy": "label",
                "scaler": "none",
                "auto_drop_ids": False,
            },
        }

        with (
            patch(
                "app.agents.data_preprocessing_agent.get_upload_stored_path_by_file_id",
                return_value=str(sample_csv),
            ),
            patch(
                "app.agents.data_preprocessing_agent.get_upload_schema_by_file_id",
                return_value=sample_schema_profile,
            ),
            patch(
                "app.agents.data_preprocessing_agent.get_agent_config",
                return_value={"defaults": {}},
            ),
            patch("app.agents.data_preprocessing_agent.UPLOAD_DIR", tmp_path),
        ):
            result = await data_preprocessing_handler(payload)

        assert result["status"] == "success"
        assert "encode_categorical" in result["result"]["transformations_applied"]

    @pytest.mark.asyncio
    async def test_deduplication_applied(self, tmp_path: Path, sample_csv: Path, sample_schema_profile: dict):
        from unittest.mock import patch
        from app.agents.data_preprocessing_agent import data_preprocessing_handler

        payload = {
            "dataset_id": "sample.csv",
            "step": "preprocess_data",
            "agent": "data_preprocessing_agent",
            "config": {
                "drop_duplicates": True,
                "scaler": "none",
                "encoding_strategy": "label",
                "auto_drop_ids": False,
            },
        }

        with (
            patch(
                "app.agents.data_preprocessing_agent.get_upload_stored_path_by_file_id",
                return_value=str(sample_csv),
            ),
            patch(
                "app.agents.data_preprocessing_agent.get_upload_schema_by_file_id",
                return_value=sample_schema_profile,
            ),
            patch(
                "app.agents.data_preprocessing_agent.get_agent_config",
                return_value={"defaults": {}},
            ),
            patch("app.agents.data_preprocessing_agent.UPLOAD_DIR", tmp_path),
        ):
            result = await data_preprocessing_handler(payload)

        # Sample CSV has 11 rows with 1 exact duplicate
        assert result["status"] == "success"
        assert result["result"]["rows_input"] == 11
        assert result["result"]["rows_output"] == 10
        assert "drop_duplicates" in result["result"]["transformations_applied"]
