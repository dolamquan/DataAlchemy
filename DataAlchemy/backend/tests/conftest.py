"""Shared pytest fixtures for agent tests."""

from __future__ import annotations

import csv
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Path setup — allow imports from backend/app without installing the package
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


# ---------------------------------------------------------------------------
# Minimal sample CSV with known properties:
#   - 'id'      : integer, unique per row → auto-detected as ID column
#   - 'program' : categorical, 2 values  → should be encoded
#   - 'week_0'–'week_3': numeric with a few NA values
#   - 'week_4'  : numeric with more NAs (~30% null)
#   - 'dup_*'   : last two rows are intentional duplicates
# ---------------------------------------------------------------------------
SAMPLE_CSV_CONTENT = """\
id,program,week_0,week_1,week_2,week_3,week_4
1,A,10,11,12,13,14
2,B,20,21,22,23,24
3,A,30,31,32,NA,34
4,B,40,41,42,43,NA
5,A,50,51,52,53,54
6,B,60,61,62,63,64
7,A,70,71,NA,73,74
8,B,80,81,82,83,NA
9,A,90,91,92,93,NA
10,B,100,101,102,NA,NA
10,B,100,101,102,NA,NA
"""


@pytest.fixture()
def sample_csv(tmp_path: Path) -> Path:
    """Write the sample CSV to a temp file and return its Path."""
    p = tmp_path / "sample.csv"
    p.write_text(SAMPLE_CSV_CONTENT, encoding="utf-8")
    return p


@pytest.fixture()
def sample_schema_profile(sample_csv: Path) -> dict[str, Any]:
    """Build a real schema profile from the sample CSV using the existing profiler."""
    from app.services.schema_profiler import profile_csv
    return profile_csv(str(sample_csv))


@pytest.fixture()
def sample_rows(sample_csv: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return (fieldnames, rows) for the sample CSV."""
    from app.services.schema_profiler import normalize_value, safe_open_csv
    rows: list[dict[str, str]] = []
    with safe_open_csv(str(sample_csv)) as f:
        reader = csv.DictReader(f)
        fieldnames = [str(n).strip() for n in (reader.fieldnames or [])]
        for row in reader:
            rows.append({col: normalize_value(row.get(col, "")) for col in fieldnames})
    return fieldnames, rows
