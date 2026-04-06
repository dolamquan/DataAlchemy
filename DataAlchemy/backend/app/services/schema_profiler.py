import csv
from collections import Counter
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
            null_count = sum(1 for v in values if is_null_like(v))
            non_null_count = len(values) - null_count
            inferred_dtype = infer_column_type(values)

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
                    "non_null_count": non_null_count,
                    "null_count": null_count,
                    "null_ratio": round((null_count / len(values)), 4) if values else 0.0,
                    "unique_count": len(unique_trackers[column]),
                    "sample_values": non_null_examples,
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