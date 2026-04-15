"""Data Quality Agent — validates CSV data across multiple quality dimensions.

Each check returns a result dict with keys:
  check   : str            — check name
  status  : "pass"|"warn"|"fail"
  columns : list[str]      — columns involved (empty when check is row-level)
  details : str            — human-readable explanation

The overall quality_score is the mean check score (pass=1, warn=0.5, fail=0).
"""

from __future__ import annotations

import csv
import json
import math
import traceback
from collections import Counter
from pathlib import Path
from statistics import mean, stdev
from typing import Any

from app.db.models import get_upload_schema_by_file_id, get_upload_stored_path_by_file_id
from app.engine.registry import get_agent_config
from app.services.schema_profiler import is_null_like, normalize_value, safe_open_csv


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_STATUS_SCORE: dict[str, float] = {"pass": 1.0, "warn": 0.5, "fail": 0.0}


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Return the p-th percentile (0–100) of an already-sorted list."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    idx = (pct / 100) * (n - 1)
    lower = int(idx)
    upper = lower + 1
    if upper >= n:
        return sorted_values[lower]
    frac = idx - lower
    return sorted_values[lower] + frac * (sorted_values[upper] - sorted_values[lower])


def _read_all_rows(path: str) -> tuple[list[str], list[dict[str, str]]]:
    """Read entire CSV; return (fieldnames, rows) where each row is {col: raw_str}."""
    rows: list[dict[str, str]] = []
    with safe_open_csv(path) as f:
        reader = csv.DictReader(f)
        fieldnames = [str(n).strip() for n in (reader.fieldnames or [])]
        for row in reader:
            rows.append({col: normalize_value(row.get(col, "")) for col in fieldnames})
    return fieldnames, rows


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_missing_values(
    schema_profile: dict[str, Any],
    null_threshold: float,
) -> dict[str, Any]:
    """Flag columns whose null ratio exceeds *null_threshold*."""
    flagged: list[str] = []
    warn_cols: list[str] = []

    for col in schema_profile.get("columns", []):
        ratio = col.get("null_ratio", 0.0)
        if ratio >= null_threshold:
            flagged.append(f"{col['name']} ({ratio:.0%})")
        elif ratio > 0.0:
            warn_cols.append(f"{col['name']} ({ratio:.0%})")

    if flagged:
        status = "fail"
        details = (
            f"{len(flagged)} column(s) exceed the {null_threshold:.0%} null threshold: "
            + ", ".join(flagged)
        )
        columns = [f.split(" ")[0] for f in flagged]
    elif warn_cols:
        status = "warn"
        details = f"Minor missing data in: {', '.join(warn_cols)}"
        columns = [w.split(" ")[0] for w in warn_cols]
    else:
        status = "pass"
        details = "No columns exceed the null threshold."
        columns = []

    return {"check": "missing_values", "status": status, "columns": columns, "details": details}


def check_duplicates(rows: list[dict[str, str]], fieldnames: list[str]) -> dict[str, Any]:
    """Count exact-duplicate rows (all columns identical)."""
    seen: set[tuple[str, ...]] = set()
    dup_count = 0
    for row in rows:
        key = tuple(row.get(c, "") for c in fieldnames)
        if key in seen:
            dup_count += 1
        else:
            seen.add(key)

    total = len(rows)
    if dup_count == 0:
        status = "pass"
        details = "No duplicate rows detected."
    elif dup_count / total < 0.05:
        status = "warn"
        details = f"{dup_count} duplicate row(s) found ({dup_count / total:.1%} of {total})."
    else:
        status = "fail"
        details = f"{dup_count} duplicate row(s) found ({dup_count / total:.1%} of {total})."

    return {"check": "duplicate_rows", "status": status, "columns": [], "details": details}


def check_outliers_iqr(
    rows: list[dict[str, str]],
    schema_profile: dict[str, Any],
    outlier_columns: list[str] | None,
) -> dict[str, Any]:
    """IQR-based outlier detection for numeric columns."""
    numeric_cols = [
        c["name"]
        for c in schema_profile.get("columns", [])
        if c.get("inferred_dtype") in {"integer", "float"}
    ]
    if outlier_columns:
        numeric_cols = [c for c in numeric_cols if c in outlier_columns]

    flagged: list[str] = []
    for col in numeric_cols:
        values: list[float] = []
        for row in rows:
            raw = row.get(col, "")
            if is_null_like(raw):
                continue
            try:
                values.append(float(raw))
            except ValueError:
                pass
        if len(values) < 4:
            continue
        values.sort()
        q1 = _percentile(values, 25)
        q3 = _percentile(values, 75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outlier_count = sum(1 for v in values if v < lower or v > upper)
        if outlier_count > 0:
            flagged.append(f"{col} ({outlier_count} outlier(s))")

    if not flagged:
        status = "pass"
        details = "No IQR outliers detected in numeric columns."
        columns: list[str] = []
    elif len(flagged) / max(len(numeric_cols), 1) < 0.5:
        status = "warn"
        details = "IQR outliers detected: " + ", ".join(flagged)
        columns = [f.split(" ")[0] for f in flagged]
    else:
        status = "fail"
        details = "Widespread IQR outliers detected: " + ", ".join(flagged)
        columns = [f.split(" ")[0] for f in flagged]

    return {"check": "outliers_iqr", "status": status, "columns": columns, "details": details}


def check_outliers_zscore(
    rows: list[dict[str, str]],
    schema_profile: dict[str, Any],
    outlier_columns: list[str] | None,
    zscore_threshold: float = 3.0,
) -> dict[str, Any]:
    """Z-score-based outlier detection for numeric columns."""
    numeric_cols = [
        c["name"]
        for c in schema_profile.get("columns", [])
        if c.get("inferred_dtype") in {"integer", "float"}
    ]
    if outlier_columns:
        numeric_cols = [c for c in numeric_cols if c in outlier_columns]

    flagged: list[str] = []
    for col in numeric_cols:
        values: list[float] = []
        for row in rows:
            raw = row.get(col, "")
            if is_null_like(raw):
                continue
            try:
                values.append(float(raw))
            except ValueError:
                pass
        if len(values) < 4:
            continue
        mu = mean(values)
        try:
            sd = stdev(values)
        except Exception:
            continue
        if sd == 0:
            continue
        outlier_count = sum(1 for v in values if abs((v - mu) / sd) > zscore_threshold)
        if outlier_count > 0:
            flagged.append(f"{col} ({outlier_count} outlier(s))")

    if not flagged:
        status = "pass"
        details = "No z-score outliers detected in numeric columns."
        columns: list[str] = []
    elif len(flagged) / max(len(numeric_cols), 1) < 0.5:
        status = "warn"
        details = "Z-score outliers detected: " + ", ".join(flagged)
        columns = [f.split(" ")[0] for f in flagged]
    else:
        status = "fail"
        details = "Widespread z-score outliers detected: " + ", ".join(flagged)
        columns = [f.split(" ")[0] for f in flagged]

    return {"check": "outliers_zscore", "status": status, "columns": columns, "details": details}


def check_type_consistency(
    rows: list[dict[str, str]],
    schema_profile: dict[str, Any],
    columns_to_validate: list[str] | None,
) -> dict[str, Any]:
    """Re-validate inferred dtypes from the schema against actual values in the full file."""
    from app.services.schema_profiler import infer_column_type

    schema_cols = {c["name"]: c["inferred_dtype"] for c in schema_profile.get("columns", [])}
    if columns_to_validate:
        schema_cols = {k: v for k, v in schema_cols.items() if k in columns_to_validate}

    mismatches: list[str] = []
    for col, expected_dtype in schema_cols.items():
        values = [row.get(col, "") for row in rows]
        actual_dtype = infer_column_type(values)
        # Allow integer→float promotion (common with sparse data)
        if actual_dtype != expected_dtype:
            if not (expected_dtype == "integer" and actual_dtype in {"float", "categorical"}):
                mismatches.append(f"{col} (expected={expected_dtype}, actual={actual_dtype})")

    if not mismatches:
        status = "pass"
        details = "All column types are consistent with the schema profile."
        columns: list[str] = []
    else:
        status = "warn"
        details = "Type mismatches detected: " + ", ".join(mismatches)
        columns = [m.split(" ")[0] for m in mismatches]

    return {"check": "type_consistency", "status": status, "columns": columns, "details": details}


def check_cardinality(schema_profile: dict[str, Any], rows_sampled: int) -> dict[str, Any]:
    """Flag string/categorical columns where unique_count equals total rows (likely ID columns)."""
    flagged: list[str] = []
    for col in schema_profile.get("columns", []):
        if col.get("inferred_dtype") in {"string", "categorical"}:
            unique = col.get("unique_count", 0)
            if unique >= rows_sampled and rows_sampled > 0:
                flagged.append(col["name"])

    if not flagged:
        status = "pass"
        details = "No high-cardinality ID-like columns detected."
        columns: list[str] = []
    else:
        status = "warn"
        details = (
            f"Likely ID columns (unique_count ≈ row_count): {', '.join(flagged)}. "
            "Consider dropping these before modeling."
        )
        columns = flagged

    return {"check": "high_cardinality", "status": status, "columns": columns, "details": details}


def check_class_imbalance(
    rows: list[dict[str, str]],
    target_column: str | None,
    imbalance_threshold: float = 0.2,
) -> dict[str, Any]:
    """Compute class distribution for the target column; flag severe imbalance."""
    if not target_column:
        return {
            "check": "class_imbalance",
            "status": "pass",
            "columns": [],
            "details": "No target column specified; class imbalance check skipped.",
        }

    values = [row.get(target_column, "") for row in rows if not is_null_like(row.get(target_column, ""))]
    if not values:
        return {
            "check": "class_imbalance",
            "status": "warn",
            "columns": [target_column],
            "details": f"Target column '{target_column}' has no non-null values.",
        }

    counts = Counter(values)
    total = len(values)
    min_ratio = min(counts.values()) / total
    distribution = {k: round(v / total, 4) for k, v in counts.most_common()}

    if min_ratio < imbalance_threshold:
        status = "warn"
        details = (
            f"Class imbalance detected in '{target_column}'. "
            f"Minority class ratio: {min_ratio:.1%}. Distribution: {distribution}"
        )
    else:
        status = "pass"
        details = f"'{target_column}' class distribution is balanced: {distribution}"

    return {"check": "class_imbalance", "status": status, "columns": [target_column], "details": details}


def check_zero_variance(schema_profile: dict[str, Any]) -> dict[str, Any]:
    """Flag columns where all non-null values are identical (unique_count == 1)."""
    flagged: list[str] = []
    for col in schema_profile.get("columns", []):
        non_null = col.get("non_null_count", 0)
        unique = col.get("unique_count", 0)
        if non_null > 0 and unique == 1:
            flagged.append(col["name"])

    if not flagged:
        status = "pass"
        details = "No zero-variance (constant) columns detected."
        columns: list[str] = []
    else:
        status = "warn"
        details = f"Constant columns (unique_count=1): {', '.join(flagged)}. These carry no information."
        columns = flagged

    return {"check": "zero_variance", "status": status, "columns": columns, "details": details}


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------

def _resolve_config(payload_config: dict[str, Any]) -> dict[str, Any]:
    """Merge agent defaults from agents.yaml with caller-supplied overrides."""
    try:
        agent_cfg = get_agent_config("data_quality_agent")
        defaults: dict[str, Any] = agent_cfg.get("defaults", {})
    except KeyError:
        defaults = {}

    resolved = {
        "null_threshold": 0.30,
        "outlier_method": "iqr",
        "flag_id_columns": True,
        "check_duplicates": True,
        "outlier_columns": None,
        "columns_to_validate": None,
        "target_column": None,
        "imbalance_threshold": 0.20,
    }
    resolved.update(defaults)
    resolved.update({k: v for k, v in payload_config.items() if v is not None})
    return resolved


# ---------------------------------------------------------------------------
# Quality score computation
# ---------------------------------------------------------------------------

def _compute_quality_score(checks: list[dict[str, Any]]) -> float:
    if not checks:
        return 1.0
    total = sum(_STATUS_SCORE.get(c["status"], 0.0) for c in checks)
    return round(total / len(checks), 4)


# ---------------------------------------------------------------------------
# Recommendation engine
# ---------------------------------------------------------------------------

def _build_recommendations(checks: list[dict[str, Any]]) -> list[str]:
    recs: list[str] = []
    for c in checks:
        if c["status"] in {"warn", "fail"}:
            check = c["check"]
            cols = c.get("columns", [])
            if check == "missing_values":
                recs.append(
                    f"Impute or drop columns with high null ratios: {', '.join(cols)}."
                )
            elif check == "duplicate_rows":
                recs.append("Remove duplicate rows before training to avoid data leakage.")
            elif check in {"outliers_iqr", "outliers_zscore"}:
                recs.append(
                    f"Investigate and handle outliers in: {', '.join(cols)}. "
                    "Consider capping, transforming, or removing extreme values."
                )
            elif check == "type_consistency":
                recs.append(
                    f"Review type inference for columns: {', '.join(cols)}. "
                    "Mixed types may indicate parsing issues."
                )
            elif check == "high_cardinality":
                recs.append(
                    f"Drop or hash high-cardinality columns before modeling: {', '.join(cols)}."
                )
            elif check == "class_imbalance":
                recs.append(
                    f"Apply resampling (SMOTE, oversampling, or class weights) "
                    f"for imbalanced target column: {', '.join(cols)}."
                )
            elif check == "zero_variance":
                recs.append(
                    f"Drop constant columns — they carry no predictive signal: {', '.join(cols)}."
                )
    return recs


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------

async def data_quality_handler(payload: dict[str, Any]) -> dict[str, Any]:
    """Async handler registered with agent_runtime for 'data_quality_agent'."""
    step = payload.get("step", "data_quality")
    dataset_id: str = payload.get("dataset_id", "")
    cfg = _resolve_config(payload.get("config") or {})

    # --- locate file on disk ---
    stored_path = get_upload_stored_path_by_file_id(dataset_id)
    if stored_path is None:
        return _failed(step, f"Dataset '{dataset_id}' not found in database.")

    if not Path(stored_path).exists():
        # fall back: try UPLOAD_DIR / dataset_id (file_id is stored filename)
        from app.core.settings import UPLOAD_DIR
        alt = UPLOAD_DIR / dataset_id
        if alt.exists():
            stored_path = str(alt)
        else:
            return _failed(step, f"File not found on disk: {stored_path}")

    # --- load schema profile ---
    schema_profile = get_upload_schema_by_file_id(dataset_id)
    if schema_profile is None:
        return _failed(step, f"Schema profile not found for dataset '{dataset_id}'.")

    # --- read full CSV ---
    try:
        fieldnames, rows = _read_all_rows(stored_path)
    except Exception as exc:
        return _failed(step, f"Could not read CSV: {exc}\n{traceback.format_exc()}")

    if not rows:
        return _failed(step, "CSV file contains no data rows.")

    rows_sampled = schema_profile.get("rows_sampled", len(rows))

    # --- run checks ---
    checks: list[dict[str, Any]] = []

    checks.append(
        check_missing_values(schema_profile, float(cfg["null_threshold"]))
    )

    if cfg.get("check_duplicates", True):
        checks.append(check_duplicates(rows, fieldnames))

    outlier_method = str(cfg.get("outlier_method", "iqr")).lower()
    outlier_columns = cfg.get("outlier_columns")
    if outlier_method == "iqr":
        checks.append(check_outliers_iqr(rows, schema_profile, outlier_columns))
    elif outlier_method == "zscore":
        checks.append(check_outliers_zscore(rows, schema_profile, outlier_columns))

    checks.append(
        check_type_consistency(rows, schema_profile, cfg.get("columns_to_validate"))
    )

    if cfg.get("flag_id_columns", True):
        checks.append(check_cardinality(schema_profile, rows_sampled))

    checks.append(
        check_class_imbalance(rows, cfg.get("target_column"), float(cfg.get("imbalance_threshold", 0.20)))
    )

    checks.append(check_zero_variance(schema_profile))

    # --- aggregate ---
    quality_score = _compute_quality_score(checks)
    recommendations = _build_recommendations(checks)

    result_data = {
        "quality_score": quality_score,
        "checks": checks,
        "recommendations": recommendations,
    }

    return {
        "status": "success",
        "result": result_data,
        "artifacts": [
            {
                "name": "quality_report.json",
                "type": "json",
                "data": result_data,
            }
        ],
        "dashboard_updates": [
            {
                "agent": "data_quality_agent",
                "step": step,
                "status": "completed",
                "message": f"Quality score: {quality_score:.2f}",
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
                "agent": "data_quality_agent",
                "step": step,
                "status": "failed",
                "message": message,
            }
        ],
    }
