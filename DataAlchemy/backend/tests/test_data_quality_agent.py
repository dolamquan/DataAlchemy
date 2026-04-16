"""Unit tests for the data_quality_agent module."""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# check_missing_values
# ---------------------------------------------------------------------------

class TestCheckMissingValues:
    def test_pass_when_no_nulls(self):
        from app.agents.data_quality_agent import check_missing_values
        profile = {
            "columns": [
                {"name": "a", "null_ratio": 0.0},
                {"name": "b", "null_ratio": 0.0},
            ]
        }
        result = check_missing_values(profile, null_threshold=0.30)
        assert result["status"] == "pass"
        assert result["columns"] == []

    def test_warn_when_minor_nulls_below_threshold(self):
        from app.agents.data_quality_agent import check_missing_values
        profile = {
            "columns": [
                {"name": "a", "null_ratio": 0.10},
            ]
        }
        result = check_missing_values(profile, null_threshold=0.30)
        assert result["status"] == "warn"
        assert "a" in result["columns"]

    def test_fail_when_null_ratio_at_threshold(self):
        from app.agents.data_quality_agent import check_missing_values
        profile = {
            "columns": [
                {"name": "x", "null_ratio": 0.30},
            ]
        }
        result = check_missing_values(profile, null_threshold=0.30)
        assert result["status"] == "fail"
        assert "x" in result["columns"]

    def test_multiple_columns_only_flagged_exceeding(self):
        from app.agents.data_quality_agent import check_missing_values
        profile = {
            "columns": [
                {"name": "ok", "null_ratio": 0.05},
                {"name": "bad", "null_ratio": 0.50},
            ]
        }
        result = check_missing_values(profile, null_threshold=0.30)
        assert result["status"] == "fail"
        assert "bad" in result["columns"]
        assert "ok" not in result["columns"]


# ---------------------------------------------------------------------------
# check_duplicates
# ---------------------------------------------------------------------------

class TestCheckDuplicates:
    def test_no_duplicates(self):
        from app.agents.data_quality_agent import check_duplicates
        rows = [{"a": "1"}, {"a": "2"}, {"a": "3"}]
        result = check_duplicates(rows, ["a"])
        assert result["status"] == "pass"

    def test_few_duplicates_warn(self):
        from app.agents.data_quality_agent import check_duplicates
        rows = [{"a": str(i)} for i in range(20)] + [{"a": "0"}]
        result = check_duplicates(rows, ["a"])
        assert result["status"] == "warn"
        assert "1 duplicate" in result["details"]

    def test_many_duplicates_fail(self):
        from app.agents.data_quality_agent import check_duplicates
        rows = [{"a": "x"}] * 10 + [{"a": "y"}]
        result = check_duplicates(rows, ["a"])
        assert result["status"] == "fail"

    def test_uses_all_columns_for_dedup_key(self):
        from app.agents.data_quality_agent import check_duplicates
        # Same 'a' but different 'b' → not a duplicate
        rows = [{"a": "1", "b": "X"}, {"a": "1", "b": "Y"}]
        result = check_duplicates(rows, ["a", "b"])
        assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# check_outliers_iqr
# ---------------------------------------------------------------------------

class TestCheckOutliersIQR:
    def _make_profile(self, col_name: str, dtype: str = "float") -> dict[str, Any]:
        return {"columns": [{"name": col_name, "inferred_dtype": dtype}]}

    def test_no_outliers(self):
        from app.agents.data_quality_agent import check_outliers_iqr
        rows = [{"x": str(i)} for i in range(1, 21)]
        profile = self._make_profile("x")
        result = check_outliers_iqr(rows, profile, outlier_columns=None)
        assert result["status"] == "pass"

    def test_detects_extreme_outlier(self):
        from app.agents.data_quality_agent import check_outliers_iqr
        rows = [{"x": str(i)} for i in range(1, 20)] + [{"x": "10000"}]
        profile = self._make_profile("x")
        result = check_outliers_iqr(rows, profile, outlier_columns=None)
        assert result["status"] in {"warn", "fail"}
        assert "x" in result["columns"]

    def test_respects_outlier_columns_filter(self):
        from app.agents.data_quality_agent import check_outliers_iqr
        rows = [{"x": str(i), "y": str(i)} for i in range(1, 20)] + [{"x": "10000", "y": "10000"}]
        profile = {"columns": [
            {"name": "x", "inferred_dtype": "float"},
            {"name": "y", "inferred_dtype": "float"},
        ]}
        result = check_outliers_iqr(rows, profile, outlier_columns=["x"])
        # Only "x" should be in scope
        assert "y" not in result["columns"]

    def test_skips_non_numeric_columns(self):
        from app.agents.data_quality_agent import check_outliers_iqr
        rows = [{"cat": "foo"}] * 10
        profile = {"columns": [{"name": "cat", "inferred_dtype": "categorical"}]}
        result = check_outliers_iqr(rows, profile, outlier_columns=None)
        assert result["status"] == "pass"

    def test_too_few_values_skipped(self):
        from app.agents.data_quality_agent import check_outliers_iqr
        rows = [{"x": "1"}, {"x": "2"}]
        profile = self._make_profile("x")
        result = check_outliers_iqr(rows, profile, outlier_columns=None)
        assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# check_outliers_zscore
# ---------------------------------------------------------------------------

class TestCheckOutliersZScore:
    def test_no_outliers(self):
        from app.agents.data_quality_agent import check_outliers_zscore
        rows = [{"x": str(i)} for i in range(1, 21)]
        profile = {"columns": [{"name": "x", "inferred_dtype": "float"}]}
        result = check_outliers_zscore(rows, profile, outlier_columns=None)
        assert result["status"] == "pass"

    def test_detects_extreme_outlier(self):
        from app.agents.data_quality_agent import check_outliers_zscore
        rows = [{"x": str(i)} for i in range(1, 20)] + [{"x": "100000"}]
        profile = {"columns": [{"name": "x", "inferred_dtype": "float"}]}
        result = check_outliers_zscore(rows, profile, outlier_columns=None)
        assert result["status"] in {"warn", "fail"}
        assert "x" in result["columns"]


# ---------------------------------------------------------------------------
# check_type_consistency
# ---------------------------------------------------------------------------

class TestCheckTypeConsistency:
    def test_consistent_types(self):
        from app.agents.data_quality_agent import check_type_consistency
        rows = [{"age": "25"}, {"age": "30"}]
        profile = {"columns": [{"name": "age", "inferred_dtype": "integer"}]}
        result = check_type_consistency(rows, profile, columns_to_validate=None)
        assert result["status"] == "pass"

    def test_detects_mismatch(self):
        from app.agents.data_quality_agent import check_type_consistency
        # Schema says integer but all values are strings
        rows = [{"name": "alice"}, {"name": "bob"}, {"name": "charlie"},
                {"name": "dave"}, {"name": "eve"}, {"name": "frank"}]
        profile = {"columns": [{"name": "name", "inferred_dtype": "integer"}]}
        result = check_type_consistency(rows, profile, columns_to_validate=None)
        assert result["status"] == "warn"
        assert "name" in result["columns"]

    def test_respects_columns_to_validate_filter(self):
        from app.agents.data_quality_agent import check_type_consistency
        rows = [{"a": "hello"}, {"a": "world"}]
        profile = {"columns": [{"name": "a", "inferred_dtype": "integer"}]}
        # Filter excludes "a" → should pass
        result = check_type_consistency(rows, profile, columns_to_validate=["b"])
        assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# check_cardinality
# ---------------------------------------------------------------------------

class TestCheckCardinality:
    def test_no_high_cardinality(self):
        from app.agents.data_quality_agent import check_cardinality
        profile = {"columns": [
            {"name": "status", "inferred_dtype": "categorical", "unique_count": 3},
        ]}
        result = check_cardinality(profile, rows_sampled=100)
        assert result["status"] == "pass"

    def test_flags_id_like_column(self):
        from app.agents.data_quality_agent import check_cardinality
        profile = {"columns": [
            {"name": "user_id", "inferred_dtype": "string", "unique_count": 100},
        ]}
        result = check_cardinality(profile, rows_sampled=100)
        assert result["status"] == "warn"
        assert "user_id" in result["columns"]

    def test_ignores_numeric_columns(self):
        from app.agents.data_quality_agent import check_cardinality
        # Numeric columns are not checked for cardinality
        profile = {"columns": [
            {"name": "amount", "inferred_dtype": "float", "unique_count": 500},
        ]}
        result = check_cardinality(profile, rows_sampled=500)
        assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# check_class_imbalance
# ---------------------------------------------------------------------------

class TestCheckClassImbalance:
    def test_no_target_skips(self):
        from app.agents.data_quality_agent import check_class_imbalance
        rows = [{"y": "1"}] * 10
        result = check_class_imbalance(rows, target_column=None)
        assert result["status"] == "pass"

    def test_balanced_classes(self):
        from app.agents.data_quality_agent import check_class_imbalance
        rows = [{"y": "0"}] * 50 + [{"y": "1"}] * 50
        result = check_class_imbalance(rows, target_column="y")
        assert result["status"] == "pass"

    def test_imbalanced_classes(self):
        from app.agents.data_quality_agent import check_class_imbalance
        rows = [{"y": "0"}] * 95 + [{"y": "1"}] * 5
        result = check_class_imbalance(rows, target_column="y", imbalance_threshold=0.20)
        assert result["status"] == "warn"

    def test_missing_target_column_values(self):
        from app.agents.data_quality_agent import check_class_imbalance
        rows = [{"y": ""}, {"y": "NA"}]
        result = check_class_imbalance(rows, target_column="y")
        assert result["status"] == "warn"


# ---------------------------------------------------------------------------
# check_zero_variance
# ---------------------------------------------------------------------------

class TestCheckZeroVariance:
    def test_no_constant_columns(self):
        from app.agents.data_quality_agent import check_zero_variance
        profile = {"columns": [
            {"name": "a", "non_null_count": 10, "unique_count": 5},
        ]}
        result = check_zero_variance(profile)
        assert result["status"] == "pass"

    def test_flags_constant_column(self):
        from app.agents.data_quality_agent import check_zero_variance
        profile = {"columns": [
            {"name": "const", "non_null_count": 10, "unique_count": 1},
        ]}
        result = check_zero_variance(profile)
        assert result["status"] == "warn"
        assert "const" in result["columns"]

    def test_all_null_column_not_flagged(self):
        from app.agents.data_quality_agent import check_zero_variance
        profile = {"columns": [
            {"name": "empty", "non_null_count": 0, "unique_count": 0},
        ]}
        result = check_zero_variance(profile)
        assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# Quality score + recommendations
# ---------------------------------------------------------------------------

class TestQualityScoreAndRecommendations:
    def test_all_pass_gives_score_one(self):
        from app.agents.data_quality_agent import _compute_quality_score
        checks = [
            {"status": "pass"},
            {"status": "pass"},
            {"status": "pass"},
        ]
        assert _compute_quality_score(checks) == 1.0

    def test_mixed_gives_correct_score(self):
        from app.agents.data_quality_agent import _compute_quality_score
        checks = [
            {"status": "pass"},   # 1.0
            {"status": "warn"},   # 0.5
            {"status": "fail"},   # 0.0
        ]
        score = _compute_quality_score(checks)
        assert abs(score - 0.5) < 1e-6

    def test_recommendations_generated_for_non_pass(self):
        from app.agents.data_quality_agent import _build_recommendations
        checks = [
            {"check": "missing_values", "status": "fail", "columns": ["col_a"], "details": ""},
            {"check": "duplicate_rows", "status": "warn", "columns": [], "details": ""},
        ]
        recs = _build_recommendations(checks)
        assert len(recs) == 2
        assert any("impute" in r.lower() or "drop" in r.lower() for r in recs)

    def test_no_recommendations_when_all_pass(self):
        from app.agents.data_quality_agent import _build_recommendations
        checks = [{"check": "missing_values", "status": "pass", "columns": [], "details": ""}]
        recs = _build_recommendations(checks)
        assert recs == []


# ---------------------------------------------------------------------------
# Full handler integration (file on disk, no DB)
# ---------------------------------------------------------------------------

class TestDataQualityHandlerIntegration:
    """End-to-end test of data_quality_handler using a patched DB lookup."""

    @pytest.mark.asyncio
    async def test_full_handler_success(self, sample_csv: Path, sample_schema_profile: dict):
        from unittest.mock import patch
        from app.agents.data_quality_agent import data_quality_handler

        payload = {
            "dataset_id": "test_file.csv",
            "step": "validate_data",
            "agent": "data_quality_agent",
            "config": {"target_column": "week_4"},
        }

        with (
            patch(
                "app.agents.data_quality_agent.get_upload_stored_path_by_file_id",
                return_value=str(sample_csv),
            ),
            patch(
                "app.agents.data_quality_agent.get_upload_schema_by_file_id",
                return_value=sample_schema_profile,
            ),
            patch(
                "app.agents.data_quality_agent.get_agent_config",
                return_value={"defaults": {}},
            ),
        ):
            result = await data_quality_handler(payload)

        assert result["status"] == "success"
        assert "quality_score" in result["result"]
        assert 0.0 <= result["result"]["quality_score"] <= 1.0
        assert isinstance(result["result"]["checks"], list)
        assert len(result["result"]["checks"]) > 0
        assert isinstance(result["result"]["recommendations"], list)
        assert len(result["artifacts"]) == 1
        assert result["artifacts"][0]["name"] == "quality_report.json"
        assert len(result["dashboard_updates"]) == 1

    @pytest.mark.asyncio
    async def test_handler_fails_when_file_missing(self, sample_schema_profile: dict):
        from unittest.mock import patch
        from app.agents.data_quality_agent import data_quality_handler

        payload = {
            "dataset_id": "ghost.csv",
            "step": "validate",
            "agent": "data_quality_agent",
            "config": {},
        }

        with (
            patch(
                "app.agents.data_quality_agent.get_upload_stored_path_by_file_id",
                return_value=None,
            ),
            patch(
                "app.agents.data_quality_agent.get_upload_schema_by_file_id",
                return_value=sample_schema_profile,
            ),
            patch(
                "app.agents.data_quality_agent.get_agent_config",
                return_value={"defaults": {}},
            ),
            patch("app.core.settings.UPLOAD_DIR", Path("/nonexistent/dir")),
        ):
            result = await data_quality_handler(payload)

        assert result["status"] == "failed"
        assert "error" in result["result"]

    @pytest.mark.asyncio
    async def test_handler_fails_when_schema_missing(self, sample_csv: Path):
        from unittest.mock import patch
        from app.agents.data_quality_agent import data_quality_handler

        payload = {
            "dataset_id": "test_file.csv",
            "step": "validate",
            "agent": "data_quality_agent",
            "config": {},
        }

        with (
            patch(
                "app.agents.data_quality_agent.get_upload_stored_path_by_file_id",
                return_value=str(sample_csv),
            ),
            patch(
                "app.agents.data_quality_agent.get_upload_schema_by_file_id",
                return_value=None,
            ),
            patch(
                "app.agents.data_quality_agent.get_agent_config",
                return_value={"defaults": {}},
            ),
        ):
            result = await data_quality_handler(payload)

        assert result["status"] == "failed"
