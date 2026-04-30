"""Optional PostgreSQL-backed blob store for generated artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.core.settings import ARTIFACT_DATABASE_URL

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - optional dependency at runtime
    psycopg = None
    dict_row = None


def artifact_store_configured() -> bool:
    return bool(ARTIFACT_DATABASE_URL)


def artifact_store_available() -> bool:
    return artifact_store_configured() and psycopg is not None


def _connect():
    if not artifact_store_configured():
        return None
    if psycopg is None:
        raise RuntimeError(
            "ARTIFACT_DATABASE_URL is set, but psycopg is not installed. "
            "Install backend dependencies to enable PostgreSQL artifact storage."
        )
    conn = psycopg.connect(ARTIFACT_DATABASE_URL, row_factory=dict_row)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS artifact_blobs (
            file_id TEXT PRIMARY KEY,
            content BYTEA NOT NULL,
            content_type TEXT,
            byte_size BIGINT NOT NULL,
            metadata_json TEXT,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def save_artifact_blob(
    file_id: str,
    content: bytes,
    *,
    content_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    if not artifact_store_configured():
        return False

    timestamp = datetime.now(timezone.utc)
    payload = json.dumps(metadata or {}, default=str)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO artifact_blobs (file_id, content, content_type, byte_size, metadata_json, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (file_id) DO UPDATE SET
                content = EXCLUDED.content,
                content_type = EXCLUDED.content_type,
                byte_size = EXCLUDED.byte_size,
                metadata_json = EXCLUDED.metadata_json,
                updated_at = EXCLUDED.updated_at
            """,
            (file_id, content, content_type, len(content), payload, timestamp, timestamp),
        )
        conn.commit()
    return True


def get_artifact_blob(file_id: str) -> dict[str, Any] | None:
    if not artifact_store_configured():
        return None

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT file_id, content, content_type, byte_size, metadata_json, created_at, updated_at
            FROM artifact_blobs
            WHERE file_id = %s
            """,
            (file_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "file_id": row["file_id"],
        "content": bytes(row["content"]),
        "content_type": row["content_type"],
        "byte_size": row["byte_size"],
        "metadata": json.loads(row["metadata_json"] or "{}"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def artifact_blob_exists(file_id: str) -> bool:
    if not artifact_store_configured():
        return False

    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM artifact_blobs WHERE file_id = %s",
            (file_id,),
        ).fetchone()
    return row is not None
