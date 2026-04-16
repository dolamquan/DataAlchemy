"""Data Preprocessing Agent — cleans and transforms CSV data.

Transformations (all governed by payload["config"]):
  1. Row deduplication
  2. Drop explicit columns + auto-detected ID columns
  3. Missing-value imputation  (numeric: mean/median/constant; categorical: mode/constant)
  4. One-hot or label encoding of categorical columns
  5. Standard or MinMax scaling of numeric columns
  6. Date column decomposition (year, month, day, dayofweek)
  7. Target column separation + class distribution report

The preprocessed CSV is saved to the uploads directory as
  preprocessed_{dataset_id}.csv
and its path is returned in the artifacts list.
"""

from __future__ import annotations

import csv
import math
import traceback
from collections import Counter
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any

from app.core.settings import UPLOAD_DIR
from app.db.models import get_upload_schema_by_file_id, get_upload_stored_path_by_file_id
from app.engine.registry import get_agent_config
from app.services.schema_profiler import is_null_like, normalize_value, safe_open_csv


# ---------------------------------------------------------------------------
# CSV I/O helpers
# ---------------------------------------------------------------------------

def _read_csv(path: str) -> tuple[list[str], list[dict[str, str]]]:
    """Return (fieldnames, rows) for the full CSV at *path*."""
    rows: list[dict[str, str]] = []
    with safe_open_csv(path) as f:
        reader = csv.DictReader(f)
        fieldnames = [str(n).strip() for n in (reader.fieldnames or [])]
        for row in reader:
            rows.append({col: normalize_value(row.get(col, "")) for col in fieldnames})
    return fieldnames, rows


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------

def _resolve_config(payload_config: dict[str, Any]) -> dict[str, Any]:
    """Merge agent defaults from agents.yaml with caller-supplied overrides."""
    try:
        agent_cfg = get_agent_config("data_preprocessing_agent")
        defaults: dict[str, Any] = agent_cfg.get("defaults", {})
    except KeyError:
        defaults = {}

    resolved: dict[str, Any] = {
        "impute_strategy": "mean",
        "impute_strategy_cat": "mode",
        "encoding_strategy": "onehot",
        "max_onehot_cardinality": 15,
        "scaler": "standard",
        "drop_duplicates": True,
        "auto_drop_ids": True,
        "drop_columns": [],
        "target_column": None,
        "feature_engineering": False,
    }
    resolved.update(defaults)
    resolved.update({k: v for k, v in payload_config.items() if v is not None})

    # Normalise drop_columns to list
    dc = resolved.get("drop_columns")
    if isinstance(dc, str):
        resolved["drop_columns"] = [dc]
    elif dc is None:
        resolved["drop_columns"] = []

    return resolved


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------

def deduplicate(
    rows: list[dict[str, str]], fieldnames: list[str]
) -> tuple[list[dict[str, str]], int]:
    """Remove exact-duplicate rows; return (deduped_rows, removed_count)."""
    seen: set[tuple[str, ...]] = set()
    out: list[dict[str, str]] = []
    for row in rows:
        key = tuple(row.get(c, "") for c in fieldnames)
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out, len(rows) - len(out)


def drop_columns(
    rows: list[dict[str, str]],
    fieldnames: list[str],
    schema_profile: dict[str, Any],
    explicit_drops: list[str],
    auto_drop_ids: bool,
    rows_sampled: int,
) -> tuple[list[dict[str, str]], list[str], list[str]]:
    """Drop explicit + ID columns; return (new_rows, new_fieldnames, dropped_names)."""
    to_drop: set[str] = set(explicit_drops)

    if auto_drop_ids:
        for col in schema_profile.get("columns", []):
            if col.get("inferred_dtype") in {"string", "categorical"}:
                if col.get("unique_count", 0) >= rows_sampled > 0:
                    to_drop.add(col["name"])

    dropped = [c for c in fieldnames if c in to_drop]
    new_fieldnames = [c for c in fieldnames if c not in to_drop]
    new_rows = [{c: r[c] for c in new_fieldnames} for r in rows]
    return new_rows, new_fieldnames, dropped


def impute_missing(
    rows: list[dict[str, str]],
    fieldnames: list[str],
    schema_profile: dict[str, Any],
    numeric_strategy: str,
    cat_strategy: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Fill missing values; return (new_rows, log_entries)."""
    col_meta: dict[str, str] = {c["name"]: c["inferred_dtype"] for c in schema_profile.get("columns", [])}
    log: list[dict[str, str]] = []

    fill_values: dict[str, Any] = {}
    for col in fieldnames:
        dtype = col_meta.get(col, "string")
        col_vals = [r.get(col, "") for r in rows]
        non_null = [v for v in col_vals if not is_null_like(v)]

        if dtype in {"integer", "float"}:
            numeric_vals: list[float] = []
            for v in non_null:
                try:
                    numeric_vals.append(float(v))
                except ValueError:
                    pass

            if not numeric_vals:
                fill_values[col] = 0.0
            elif numeric_strategy == "median":
                fill_values[col] = median(numeric_vals)
            elif numeric_strategy == "constant":
                fill_values[col] = 0.0
            else:  # mean (default)
                fill_values[col] = mean(numeric_vals)

            null_count = sum(1 for v in col_vals if is_null_like(v))
            if null_count:
                log.append({
                    "column": col,
                    "action": "impute_numeric",
                    "detail": f"Filled {null_count} null(s) with {numeric_strategy}={fill_values[col]:.4g}",
                })
        else:
            if not non_null:
                fill_values[col] = "missing"
            elif cat_strategy == "constant":
                fill_values[col] = "missing"
            else:  # mode (default)
                fill_values[col] = Counter(non_null).most_common(1)[0][0]

            null_count = sum(1 for v in col_vals if is_null_like(v))
            if null_count:
                log.append({
                    "column": col,
                    "action": "impute_categorical",
                    "detail": f"Filled {null_count} null(s) with {cat_strategy}='{fill_values[col]}'",
                })

    new_rows: list[dict[str, Any]] = []
    for row in rows:
        new_row: dict[str, Any] = {}
        for col in fieldnames:
            val = row.get(col, "")
            new_row[col] = fill_values[col] if is_null_like(val) else val
        new_rows.append(new_row)

    return new_rows, log


def _try_parse_date(value: str) -> dict[str, int] | None:
    """Attempt to parse common date formats; return {year, month, day, dayofweek} or None."""
    import re
    patterns = [
        r"^(\d{4})-(\d{1,2})-(\d{1,2})$",
        r"^(\d{1,2})/(\d{1,2})/(\d{4})$",
        r"^(\d{4})/(\d{1,2})/(\d{1,2})$",
    ]
    for pat in patterns:
        m = re.match(pat, value.strip())
        if m:
            g = m.groups()
            # Determine which group is year
            if len(g[0]) == 4:
                y, mo, d = int(g[0]), int(g[1]), int(g[2])
            else:
                mo, d, y = int(g[0]), int(g[1]), int(g[2])
            try:
                import datetime
                dt = datetime.date(y, mo, d)
                return {"year": dt.year, "month": dt.month, "day": dt.day, "dayofweek": dt.weekday()}
            except ValueError:
                pass
    return None


def engineer_date_features(
    rows: list[dict[str, Any]],
    fieldnames: list[str],
    schema_profile: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, str]]]:
    """Decompose detected date string columns into year/month/day/dayofweek sub-columns."""
    string_cols = [
        c["name"] for c in schema_profile.get("columns", [])
        if c.get("inferred_dtype") == "string"
    ]
    log: list[dict[str, str]] = []
    date_cols: list[str] = []

    for col in string_cols:
        if col not in fieldnames:
            continue
        sample_vals = [rows[i].get(col, "") for i in range(min(10, len(rows)))]
        sample_vals = [v for v in sample_vals if not is_null_like(str(v))]
        if sample_vals and all(_try_parse_date(str(v)) is not None for v in sample_vals):
            date_cols.append(col)

    if not date_cols:
        return rows, fieldnames, log

    new_fieldnames = list(fieldnames)
    for col in date_cols:
        new_fieldnames.remove(col)
        for part in ("year", "month", "day", "dayofweek"):
            new_fieldnames.append(f"{col}_{part}")
        log.append({
            "column": col,
            "action": "date_decomposition",
            "detail": f"Extracted year, month, day, dayofweek from '{col}'",
        })

    new_rows: list[dict[str, Any]] = []
    for row in rows:
        new_row = {c: row[c] for c in fieldnames if c not in date_cols}
        for col in date_cols:
            parsed = _try_parse_date(str(row.get(col, "")))
            if parsed:
                for part, val in parsed.items():
                    new_row[f"{col}_{part}"] = val
            else:
                for part in ("year", "month", "day", "dayofweek"):
                    new_row[f"{col}_{part}"] = ""
        new_rows.append(new_row)

    return new_rows, new_fieldnames, log


def encode_columns(
    rows: list[dict[str, Any]],
    fieldnames: list[str],
    schema_profile: dict[str, Any],
    encoding_strategy: str,
    max_onehot_cardinality: int,
    target_column: str | None,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, str]]]:
    """Encode categorical columns via one-hot or label encoding."""
    col_meta: dict[str, dict[str, Any]] = {c["name"]: c for c in schema_profile.get("columns", [])}
    log: list[dict[str, str]] = []

    categorical_cols = [
        c for c in fieldnames
        if col_meta.get(c, {}).get("inferred_dtype") in {"categorical", "string"}
        and c != target_column
        and c in col_meta
    ]

    if not categorical_cols:
        return rows, fieldnames, log

    if encoding_strategy == "label":
        for col in categorical_cols:
            unique_vals = sorted({str(r.get(col, "")) for r in rows})
            mapping = {v: i for i, v in enumerate(unique_vals)}
            for row in rows:
                row[col] = mapping.get(str(row.get(col, "")), 0)
            log.append({
                "column": col,
                "action": "label_encode",
                "detail": f"Mapped {len(mapping)} unique values to integers",
            })
        return rows, fieldnames, log

    # Default: one-hot
    new_fieldnames = [c for c in fieldnames if c not in categorical_cols]
    for col in categorical_cols:
        unique_vals = sorted({str(r.get(col, "")) for r in rows if not is_null_like(str(r.get(col, "")))})
        cardinality = len(unique_vals)
        if cardinality > max_onehot_cardinality:
            # Fall back to label encoding for high-cardinality columns
            mapping = {v: i for i, v in enumerate(unique_vals)}
            for row in rows:
                row[col] = mapping.get(str(row.get(col, "")), 0)
            new_fieldnames.append(col)
            log.append({
                "column": col,
                "action": "label_encode_fallback",
                "detail": (
                    f"Cardinality {cardinality} > max_onehot_cardinality {max_onehot_cardinality}; "
                    "used label encoding instead"
                ),
            })
        else:
            for v in unique_vals:
                new_fieldnames.append(f"{col}_{v}")
            for row in rows:
                raw = str(row.pop(col, ""))
                for v in unique_vals:
                    row[f"{col}_{v}"] = 1 if raw == v else 0
            log.append({
                "column": col,
                "action": "onehot_encode",
                "detail": f"Created {len(unique_vals)} binary columns from '{col}'",
            })

    return rows, new_fieldnames, log


def scale_columns(
    rows: list[dict[str, Any]],
    fieldnames: list[str],
    schema_profile: dict[str, Any],
    scaler: str,
    target_column: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Scale numeric columns using standard or minmax scaling."""
    if scaler == "none":
        return rows, []

    col_meta: dict[str, str] = {c["name"]: c["inferred_dtype"] for c in schema_profile.get("columns", [])}
    log: list[dict[str, str]] = []

    numeric_cols = [
        c for c in fieldnames
        if col_meta.get(c) in {"integer", "float"}
        and c != target_column
    ]

    for col in numeric_cols:
        values: list[float] = []
        for row in rows:
            try:
                values.append(float(row[col]))
            except (ValueError, TypeError):
                pass

        if not values:
            continue

        if scaler == "minmax":
            col_min = min(values)
            col_max = max(values)
            rng = col_max - col_min
            if rng == 0:
                continue
            for row in rows:
                try:
                    row[col] = round((float(row[col]) - col_min) / rng, 8)
                except (ValueError, TypeError):
                    pass
            log.append({
                "column": col,
                "action": "minmax_scale",
                "detail": f"Scaled to [0, 1] (min={col_min:.4g}, max={col_max:.4g})",
            })
        else:  # standard (default)
            mu = mean(values)
            try:
                sd = stdev(values) if len(values) > 1 else 0.0
            except Exception:
                sd = 0.0
            if sd == 0:
                continue
            for row in rows:
                try:
                    row[col] = round((float(row[col]) - mu) / sd, 8)
                except (ValueError, TypeError):
                    pass
            log.append({
                "column": col,
                "action": "standard_scale",
                "detail": f"Standardized (mean={mu:.4g}, std={sd:.4g})",
            })

    return rows, log


def separate_target(
    rows: list[dict[str, Any]],
    fieldnames: list[str],
    target_column: str | None,
) -> dict[str, Any]:
    """Return a summary of the target column distribution (does not alter rows)."""
    if not target_column or target_column not in fieldnames:
        return {}

    values = [str(r.get(target_column, "")) for r in rows if not is_null_like(str(r.get(target_column, "")))]
    counts = Counter(values)
    total = len(values)
    distribution = {k: round(v / total, 4) for k, v in counts.most_common()} if total else {}

    return {
        "target_column": target_column,
        "total_values": total,
        "class_distribution": distribution,
    }


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------

async def data_preprocessing_handler(payload: dict[str, Any]) -> dict[str, Any]:
    """Async handler registered with agent_runtime for 'data_preprocessing_agent'."""
    step = payload.get("step", "preprocess_data")
    dataset_id: str = payload.get("dataset_id", "")
    cfg = _resolve_config(payload.get("config") or {})

    # --- locate file on disk ---
    stored_path = get_upload_stored_path_by_file_id(dataset_id)
    if stored_path is None:
        # Fall back: treat dataset_id as the stored filename directly
        alt = UPLOAD_DIR / dataset_id
        if alt.exists():
            stored_path = str(alt)
        else:
            return _failed(step, f"Dataset '{dataset_id}' not found in database.")

    if not Path(stored_path).exists():
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
        fieldnames, rows = _read_csv(stored_path)
    except Exception as exc:
        return _failed(step, f"Could not read CSV: {exc}\n{traceback.format_exc()}")

    if not rows:
        return _failed(step, "CSV file contains no data rows.")

    rows_input = len(rows)
    columns_input = len(fieldnames)
    preprocessing_log: list[dict[str, str]] = []
    transformations_applied: list[str] = []
    rows_sampled = schema_profile.get("rows_sampled", rows_input)

    # 1. Deduplication
    if cfg.get("drop_duplicates", True):
        rows, removed = deduplicate(rows, fieldnames)
        if removed:
            preprocessing_log.append({
                "column": "ALL",
                "action": "drop_duplicates",
                "detail": f"Removed {removed} exact duplicate row(s)",
            })
            transformations_applied.append("drop_duplicates")

    # 2. Drop columns
    explicit_drops: list[str] = list(cfg.get("drop_columns") or [])
    auto_drop_ids: bool = bool(cfg.get("auto_drop_ids", True))
    rows, fieldnames, dropped_cols = drop_columns(
        rows, fieldnames, schema_profile, explicit_drops, auto_drop_ids, rows_sampled
    )
    if dropped_cols:
        for dc in dropped_cols:
            preprocessing_log.append({
                "column": dc,
                "action": "drop_column",
                "detail": "Dropped (explicit request or auto-detected ID column)",
            })
        transformations_applied.append("drop_columns")

    # 3. Impute missing values
    rows, impute_log = impute_missing(
        rows,
        fieldnames,
        schema_profile,
        str(cfg.get("impute_strategy", "mean")),
        str(cfg.get("impute_strategy_cat", "mode")),
    )
    if impute_log:
        preprocessing_log.extend(impute_log)
        transformations_applied.append("impute_missing")

    # 4. Date feature engineering (before encoding, so new int columns skip encoding)
    if cfg.get("feature_engineering", False):
        rows, fieldnames, date_log = engineer_date_features(rows, fieldnames, schema_profile)
        if date_log:
            preprocessing_log.extend(date_log)
            transformations_applied.append("date_decomposition")

    # 5. Encode categorical columns
    target_column: str | None = cfg.get("target_column")
    rows, fieldnames, encode_log = encode_columns(
        rows,
        fieldnames,
        schema_profile,
        str(cfg.get("encoding_strategy", "onehot")),
        int(cfg.get("max_onehot_cardinality", 15)),
        target_column,
    )
    if encode_log:
        preprocessing_log.extend(encode_log)
        transformations_applied.append("encode_categorical")

    # 6. Scale numeric columns
    scaler = str(cfg.get("scaler", "standard"))
    rows, scale_log = scale_columns(rows, fieldnames, schema_profile, scaler, target_column)
    if scale_log:
        preprocessing_log.extend(scale_log)
        transformations_applied.append(f"scale_{scaler}")

    # 7. Target summary (informational)
    target_info = separate_target(rows, fieldnames, target_column)

    # --- save preprocessed CSV ---
    out_filename = f"preprocessed_{dataset_id}"
    if not out_filename.endswith(".csv"):
        out_filename += ".csv"
    out_path = UPLOAD_DIR / out_filename
    try:
        _write_csv(out_path, fieldnames, rows)
    except Exception as exc:
        return _failed(step, f"Failed to write preprocessed CSV: {exc}\n{traceback.format_exc()}")

    result_data: dict[str, Any] = {
        "rows_input": rows_input,
        "rows_output": len(rows),
        "columns_input": columns_input,
        "columns_output": len(fieldnames),
        "transformations_applied": transformations_applied,
        "preprocessing_log": preprocessing_log,
        "preprocessed_file_id": out_filename,
    }
    if target_info:
        result_data["target_summary"] = target_info

    return {
        "status": "success",
        "result": result_data,
        "artifacts": [
            {
                "name": "preprocessed_dataset.csv",
                "type": "csv",
                "path": str(out_path),
                "file_id": out_filename,
            },
            {
                "name": "preprocessing_log.json",
                "type": "json",
                "data": preprocessing_log,
            },
        ],
        "dashboard_updates": [
            {
                "agent": "data_preprocessing_agent",
                "step": step,
                "status": "completed",
                "message": (
                    f"Preprocessed {rows_input}→{len(rows)} rows, "
                    f"{columns_input}→{len(fieldnames)} columns. "
                    f"Transforms: {', '.join(transformations_applied) or 'none'}"
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
                "agent": "data_preprocessing_agent",
                "step": step,
                "status": "failed",
                "message": message,
            }
        ],
    }
