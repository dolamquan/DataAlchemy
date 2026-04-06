import csv
from collections import Counter
from math import isfinite
from statistics import median
from pathlib import Path
from typing import Any


NULL_STRINGS = {"", "null", "none", "na", "n/a", "nan"}


def normalize_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_null_like(value: Any) -> bool:
    return normalize_value(value).lower() in NULL_STRINGS


def is_int_like(value: str) -> bool:
    try:
        int(value)
        return True
    except Exception:
        return False


def is_float_like(value: str) -> bool:
    try:
        float(value)
        return True
    except Exception:
        return False


def try_parse_float(value: str) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return None
    if not isfinite(parsed):
        return None
    return parsed


def build_numeric_distribution(values: list[float], bin_count: int = 10) -> list[dict[str, Any]]:
    if not values:
        return []

    min_value = min(values)
    max_value = max(values)

    if min_value == max_value:
        return [{"label": f"{round(min_value, 4)}", "count": len(values)}]

    safe_bins = max(3, min(bin_count, 20))
    step = (max_value - min_value) / safe_bins
    bins: list[dict[str, Any]] = []

    for i in range(safe_bins):
        start = min_value + (i * step)
        end = min_value + ((i + 1) * step)

        if i == safe_bins - 1:
            count = sum(1 for v in values if start <= v <= end)
        else:
            count = sum(1 for v in values if start <= v < end)

        bins.append(
            {
                "label": f"{round(start, 2)}-{round(end, 2)}",
                "start": round(start, 6),
                "end": round(end, 6),
                "count": count,
            }
        )

    return bins


def infer_profile_column_family(inferred_dtype: str) -> str:
    if inferred_dtype in {"integer", "float"}:
        return "numeric"
    if inferred_dtype == "boolean":
        return "boolean"
    if inferred_dtype in {"categorical", "string"}:
        return "categorical"
    return "other"


def infer_column_type(values: list[str]) -> str:
    non_null_values = [v for v in values if not is_null_like(v)]

    if not non_null_values:
        return "unknown"

    lowered = [v.lower() for v in non_null_values]

    if all(v in {"true", "false", "0", "1"} for v in lowered):
        return "boolean"

    if all(is_int_like(v) for v in non_null_values):
        return "integer"

    if all(is_float_like(v) for v in non_null_values):
        return "float"

    unique_count = len(set(non_null_values))
    total = len(non_null_values)

    if total > 0 and unique_count <= min(50, max(5, int(total * 0.2))):
        return "categorical"

    return "string"


def safe_open_csv(path: str):
    """
    Try utf-8 first, then utf-8-sig, then latin-1 as fallback.
    """
    encodings = ["utf-8", "utf-8-sig", "latin-1"]
    last_error = None

    for encoding in encodings:
        try:
            file_obj = open(path, mode="r", newline="", encoding=encoding)
            # test read lightly by returning handle only if open succeeds
            return file_obj
        except Exception as exc:
            last_error = exc

    raise last_error


def profile_csv(path: str, sample_rows: int = 500, preview_rows_count: int = 5) -> dict:
    """
    Sample-based CSV schema profiler.

    Returns:
        {
            "file_name": str,
            "stored_file_name": str,
            "file_size_bytes": int,
            "rows_sampled": int,
            "total_columns": int,
            "columns": [
                {
                    "name": str,
                    "inferred_dtype": str,
                    "non_null_count": int,
                    "null_count": int,
                    "null_ratio": float,
                    "unique_count": int,
                    "sample_values": list[str]
                }
            ],
            "preview_rows": list[dict[str, Any]],
            "notes": list[str]
        }
    """
    file_path = Path(path)
    file_size = file_path.stat().st_size

    with safe_open_csv(path) as csvfile:
        reader = csv.DictReader(csvfile)

        if not reader.fieldnames:
            raise ValueError("CSV file appears to have no header row.")

        fieldnames = [str(name).strip() if name is not None else "" for name in reader.fieldnames]

        column_values: dict[str, list[str]] = {name: [] for name in fieldnames}
        unique_trackers: dict[str, set[str]] = {name: set() for name in fieldnames}
        preview_rows: list[dict[str, Any]] = []

        sampled_count = 0

        for row in reader:
            if sampled_count >= sample_rows:
                break

            cleaned_row: dict[str, Any] = {}

            for column in fieldnames:
                raw_value = row.get(column, "")
                value = normalize_value(raw_value)

                column_values[column].append(value)
                if not is_null_like(value):
                    unique_trackers[column].add(value)

                cleaned_row[column] = value

            if len(preview_rows) < preview_rows_count:
                preview_rows.append(cleaned_row)

            sampled_count += 1

        columns = []
        for column in fieldnames:
            values = column_values[column]
            non_null_values = [v for v in values if not is_null_like(v)]
            null_count = sum(1 for v in values if is_null_like(v))
            non_null_count = len(values) - null_count
            inferred_dtype = infer_column_type(values)
            column_family = infer_profile_column_family(inferred_dtype)

            numeric_values = [v for v in (try_parse_float(item) for item in non_null_values) if v is not None]
            numeric_stats: dict[str, Any] | None = None
            numeric_distribution: list[dict[str, Any]] = []

            if column_family == "numeric" and numeric_values:
                numeric_values_sorted = sorted(numeric_values)
                numeric_stats = {
                    "min": round(min(numeric_values_sorted), 6),
                    "max": round(max(numeric_values_sorted), 6),
                    "mean": round(sum(numeric_values_sorted) / len(numeric_values_sorted), 6),
                    "median": round(float(median(numeric_values_sorted)), 6),
                }
                numeric_distribution = build_numeric_distribution(numeric_values_sorted)

            categorical_top_values: list[dict[str, Any]] = []
            if column_family == "categorical" and non_null_values:
                freq = Counter(non_null_values)
                categorical_top_values = [
                    {"value": key, "count": count}
                    for key, count in freq.most_common(10)
                ]

            # keep up to 5 sample values, excluding null-like values where possible
            non_null_examples = []
            seen = set()
            for v in values:
                if is_null_like(v):
                    continue
                if v not in seen:
                    non_null_examples.append(v)
                    seen.add(v)
                if len(non_null_examples) >= 5:
                    break

            if not non_null_examples:
                non_null_examples = values[:5]

            columns.append(
                {
                    "name": column,
                    "inferred_dtype": inferred_dtype,
                    "column_family": column_family,
                    "non_null_count": non_null_count,
                    "null_count": null_count,
                    "null_ratio": round((null_count / len(values)), 4) if values else 0.0,
                    "unique_count": len(unique_trackers[column]),
                    "sample_values": non_null_examples,
                    "numeric_stats": numeric_stats,
                    "numeric_distribution": numeric_distribution,
                    "categorical_top_values": categorical_top_values,
                }
            )

        return {
            "file_name": file_path.name,
            "stored_file_name": file_path.name,
            "file_size_bytes": file_size,
            "rows_sampled": sampled_count,
            "total_columns": len(fieldnames),
            "columns": columns,
            "preview_rows": preview_rows,
            "notes": [
                "Profile is sample-based, using the first N rows rather than the full dataset.",
                f"Rows sampled: {sampled_count}",
            ],
        }


def build_schema_insights(schema_profile: dict[str, Any], top_n: int = 8) -> dict[str, Any]:
    columns = schema_profile.get("columns") or []

    numeric_columns = [
        c for c in columns
        if (c.get("column_family") == "numeric" or c.get("inferred_dtype") in {"integer", "float"})
    ]
    categorical_columns = [
        c for c in columns
        if (c.get("column_family") == "categorical" or c.get("inferred_dtype") in {"categorical", "string"})
    ]
    boolean_columns = [c for c in columns if c.get("inferred_dtype") == "boolean"]

    columns_with_missing_values = [
        {
            "name": c.get("name"),
            "null_count": int(c.get("null_count") or 0),
            "null_ratio": float(c.get("null_ratio") or 0.0),
        }
        for c in columns
        if (c.get("null_count") or 0) > 0
    ]
    columns_with_missing_values.sort(key=lambda item: (item["null_count"], item["null_ratio"]), reverse=True)

    columns_by_unique_count = [
        {
            "name": c.get("name"),
            "unique_count": int(c.get("unique_count") or 0),
        }
        for c in columns
    ]
    columns_by_unique_count.sort(key=lambda item: item["unique_count"], reverse=True)

    numeric_distributions = [
        {
            "column": c.get("name"),
            "stats": c.get("numeric_stats") or {},
            "bins": c.get("numeric_distribution") or [],
        }
        for c in numeric_columns
        if c.get("name")
    ]

    categorical_frequencies = [
        {
            "column": c.get("name"),
            "values": c.get("categorical_top_values") or [],
        }
        for c in categorical_columns
        if c.get("name")
    ]

    return {
        "summary": {
            "total_columns": int(schema_profile.get("total_columns") or len(columns)),
            "rows_sampled": int(schema_profile.get("rows_sampled") or 0),
            "numeric_columns": len(numeric_columns),
            "categorical_columns": len(categorical_columns),
            "boolean_columns": len(boolean_columns),
            "columns_with_missing_values": len(columns_with_missing_values),
        },
        "column_type_counts": {
            "numeric": len(numeric_columns),
            "categorical": len(categorical_columns),
            "boolean": len(boolean_columns),
            "other": max(0, len(columns) - (len(numeric_columns) + len(categorical_columns) + len(boolean_columns))),
        },
        "columns_by_null_ratio": columns_with_missing_values[:top_n],
        "columns_by_unique_count": columns_by_unique_count[:top_n],
        "numeric_distributions": numeric_distributions,
        "categorical_frequencies": categorical_frequencies,
    }