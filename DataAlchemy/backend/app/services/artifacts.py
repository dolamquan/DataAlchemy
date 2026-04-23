"""Helpers for writing downloadable agent artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.core.settings import UPLOAD_DIR

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def safe_artifact_file_id(prefix: str, dataset_id: str, extension: str) -> str:
    """Build a deterministic artifact filename scoped to one dataset/run."""
    suffix = extension if extension.startswith(".") else f".{extension}"
    stem = Path(dataset_id).stem or "dataset"
    safe_stem = _SAFE_NAME_RE.sub("_", stem).strip("._") or "dataset"
    return f"{prefix}_{safe_stem}{suffix}"


def write_json_artifact(file_id: str, payload: Any) -> Path:
    """Persist JSON payload under the uploads directory for artifact download."""
    if "/" in file_id or "\\" in file_id or ".." in file_id:
        raise ValueError(f"Invalid artifact file_id: {file_id}")

    path = (UPLOAD_DIR / file_id).resolve()
    upload_dir = UPLOAD_DIR.resolve()
    if not str(path).startswith(str(upload_dir)):
        raise ValueError(f"Invalid artifact file_id: {file_id}")

    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path
