"""Tests for restoring uploaded files from DB-backed content."""

from __future__ import annotations

import shutil
import sqlite3
import uuid
from pathlib import Path


def test_resolve_upload_path_restores_missing_file_from_db(monkeypatch) -> None:
    from app.db import models
    from app.db.models import create_upload_record, init_upload_tables
    from app.services import storage

    test_root = Path.cwd() / ".tmp_pytest" / f"restore-{uuid.uuid4().hex}"
    upload_dir = test_root / "uploads"
    upload_dir.mkdir(parents=True)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    try:
        monkeypatch.setattr(models, "get_connection", lambda: conn)
        monkeypatch.setattr(storage, "UPLOAD_DIR", upload_dir)
        init_upload_tables()

        file_id = "dataset.csv"
        stored_path = upload_dir / file_id
        content = b"a,b\n1,2\n"

        create_upload_record(
            file_id=file_id,
            original_filename="dataset.csv",
            stored_path=str(stored_path),
            file_size_bytes=len(content),
            schema_profile={"columns": []},
            file_content=content,
        )

        restored_path = storage.resolve_upload_path_from_db(file_id)

        assert restored_path == stored_path
        assert restored_path.read_bytes() == content
    finally:
        conn.close()
        shutil.rmtree(test_root, ignore_errors=True)
