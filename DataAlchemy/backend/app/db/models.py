import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.session import get_connection


def init_upload_tables() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_uid TEXT,
                file_id TEXT NOT NULL UNIQUE,
                original_filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                schema_profile_json TEXT NOT NULL,
                file_content BLOB,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_uid TEXT,
                dataset_id TEXT NOT NULL UNIQUE,
                file_id TEXT NOT NULL,
                content_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_uid TEXT,
                owner_email TEXT,
                activity_type TEXT NOT NULL,
                status TEXT NOT NULL,
                resource_id TEXT,
                resource_name TEXT,
                details_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        upload_columns = {row["name"] for row in conn.execute("PRAGMA table_info(uploads)").fetchall()}
        if "file_content" not in upload_columns:
            conn.execute("ALTER TABLE uploads ADD COLUMN file_content BLOB")
        if "owner_uid" not in upload_columns:
            conn.execute("ALTER TABLE uploads ADD COLUMN owner_uid TEXT")

        report_columns = {row["name"] for row in conn.execute("PRAGMA table_info(reports)").fetchall()}
        if "owner_uid" not in report_columns:
            conn.execute("ALTER TABLE reports ADD COLUMN owner_uid TEXT")
        activity_columns = {row["name"] for row in conn.execute("PRAGMA table_info(activity_logs)").fetchall()}
        if "owner_email" not in activity_columns:
            conn.execute("ALTER TABLE activity_logs ADD COLUMN owner_email TEXT")
        if "details_json" not in activity_columns:
            conn.execute("ALTER TABLE activity_logs ADD COLUMN details_json TEXT")

        rows = conn.execute(
            """
            SELECT file_id, stored_path
            FROM uploads
            WHERE file_content IS NULL
            """
        ).fetchall()
        for row in rows:
            path = Path(row["stored_path"])
            if path.exists() and path.is_file():
                try:
                    content = path.read_bytes()
                except OSError:
                    continue
                conn.execute(
                    """
                    UPDATE uploads
                    SET file_content = ?
                    WHERE file_id = ?
                    """,
                    (content, row["file_id"]),
                )
        conn.commit()


def _user_clause(owner_uid: str | None) -> tuple[str, tuple[Any, ...]]:
    if owner_uid is None:
        return "", ()
    return " AND owner_uid = ?", (owner_uid,)


def _content_contains_file_id(value: Any, file_id: str) -> bool:
    if isinstance(value, dict):
        return any(_content_contains_file_id(item, file_id) for item in value.values())
    if isinstance(value, list):
        return any(_content_contains_file_id(item, file_id) for item in value)
    return value == file_id


def create_upload_record(
    *,
    owner_uid: str | None,
    file_id: str,
    original_filename: str,
    stored_path: str,
    file_size_bytes: int,
    schema_profile: dict[str, Any],
    file_content: bytes | None = None,
) -> None:
    payload = json.dumps(schema_profile)
    created_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO uploads (
                owner_uid,
                file_id,
                original_filename,
                stored_path,
                file_size_bytes,
                schema_profile_json,
                file_content,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                owner_uid,
                file_id,
                original_filename,
                stored_path,
                file_size_bytes,
                payload,
                file_content,
                created_at,
            ),
        )
        conn.commit()


def list_recent_upload_records(
    limit: int = 10,
    *,
    owner_uid: str | None,
    available_only: bool = True,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 100))
    where_sql, params = _user_clause(owner_uid)

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT file_id, original_filename, stored_path, file_size_bytes, created_at, file_content
            FROM uploads
            WHERE 1 = 1 {where_sql}
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (*params, max(safe_limit * 3, safe_limit)),
        ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        disk_exists = Path(row["stored_path"]).exists()
        has_db_content = row["file_content"] is not None
        is_available = disk_exists or has_db_content
        if available_only and not is_available:
            continue

        items.append(
            {
                "file_id": row["file_id"],
                "original_filename": row["original_filename"],
                "file_size_bytes": row["file_size_bytes"],
                "created_at": row["created_at"],
                "is_available": is_available,
                "storage_source": "db" if has_db_content else "disk" if disk_exists else "missing",
            }
        )
        if len(items) >= safe_limit:
            break

    return items


def get_upload_schema_by_file_id(file_id: str, *, owner_uid: str | None = None) -> dict[str, Any] | None:
    where_sql, params = _user_clause(owner_uid)
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT schema_profile_json
            FROM uploads
            WHERE file_id = ? {where_sql}
            """,
            (file_id, *params),
        ).fetchone()

    if row is None:
        return None

    return json.loads(row["schema_profile_json"])


def get_upload_record_by_file_id(file_id: str, *, owner_uid: str | None = None) -> dict[str, Any] | None:
    where_sql, params = _user_clause(owner_uid)
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT owner_uid, file_id, original_filename, stored_path, file_size_bytes, created_at
            FROM uploads
            WHERE file_id = ? {where_sql}
            """,
            (file_id, *params),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def get_upload_stored_path_by_file_id(file_id: str, *, owner_uid: str | None = None) -> str | None:
    where_sql, params = _user_clause(owner_uid)
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT stored_path
            FROM uploads
            WHERE file_id = ? {where_sql}
            """,
            (file_id, *params),
        ).fetchone()

    if row is None:
        return None

    return row["stored_path"]


def get_upload_file_content_by_file_id(file_id: str, *, owner_uid: str | None = None) -> bytes | None:
    where_sql, params = _user_clause(owner_uid)
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT file_content
            FROM uploads
            WHERE file_id = ? {where_sql}
            """,
            (file_id, *params),
        ).fetchone()

    if row is None:
        return None

    content = row["file_content"]
    return bytes(content) if content is not None else None


def save_report_record(
    *,
    owner_uid: str | None,
    dataset_id: str,
    file_id: str,
    content: dict[str, Any],
) -> None:
    init_upload_tables()
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(content)

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO reports (
                owner_uid,
                dataset_id,
                file_id,
                content_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(dataset_id) DO UPDATE SET
                owner_uid = excluded.owner_uid,
                file_id = excluded.file_id,
                content_json = excluded.content_json,
                updated_at = excluded.updated_at
            """,
            (
                owner_uid,
                dataset_id,
                file_id,
                payload,
                timestamp,
                timestamp,
            ),
        )
        conn.commit()


def get_report_record_by_dataset_id(dataset_id: str, *, owner_uid: str | None = None) -> dict[str, Any] | None:
    init_upload_tables()
    where_sql, params = _user_clause(owner_uid)
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT owner_uid, dataset_id, file_id, content_json, created_at, updated_at
            FROM reports
            WHERE dataset_id = ? {where_sql}
            """,
            (dataset_id, *params),
        ).fetchone()

    if row is None:
        return None

    return {
        "owner_uid": row["owner_uid"],
        "dataset_id": row["dataset_id"],
        "file_id": row["file_id"],
        "content": json.loads(row["content_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def user_can_access_artifact(file_id: str, *, owner_uid: str | None) -> bool:
    if owner_uid is None:
        return False

    with get_connection() as conn:
        upload_row = conn.execute(
            """
            SELECT 1
            FROM uploads
            WHERE owner_uid = ? AND file_id = ?
            """,
            (owner_uid, file_id),
        ).fetchone()
        if upload_row is not None:
            return True

        report_rows = conn.execute(
            """
            SELECT file_id, content_json
            FROM reports
            WHERE owner_uid = ?
            """,
            (owner_uid,),
        ).fetchall()

    for row in report_rows:
        if row["file_id"] == file_id:
            return True
        try:
            content = json.loads(row["content_json"])
        except json.JSONDecodeError:
            continue
        if _content_contains_file_id(content, file_id):
            return True
    return False


def log_user_activity(
    *,
    owner_uid: str | None,
    owner_email: str | None,
    activity_type: str,
    status: str,
    resource_id: str | None = None,
    resource_name: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    init_upload_tables()
    created_at = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(details or {})
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO activity_logs (
                owner_uid,
                owner_email,
                activity_type,
                status,
                resource_id,
                resource_name,
                details_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                owner_uid,
                owner_email,
                activity_type,
                status,
                resource_id,
                resource_name,
                payload,
                created_at,
            ),
        )
        conn.commit()


def list_activity_logs(limit: int = 100) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 500))
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT owner_uid, owner_email, activity_type, status, resource_id, resource_name, details_json, created_at
            FROM activity_logs
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    return [
        {
            "owner_uid": row["owner_uid"],
            "owner_email": row["owner_email"],
            "activity_type": row["activity_type"],
            "status": row["status"],
            "resource_id": row["resource_id"],
            "resource_name": row["resource_name"],
            "details": json.loads(row["details_json"] or "{}"),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def summarize_user_activity() -> list[dict[str, Any]]:
    init_upload_tables()
    with get_connection() as conn:
        upload_rows = conn.execute(
            """
            SELECT owner_uid, COUNT(*) AS upload_count, MAX(created_at) AS last_upload_at
            FROM uploads
            WHERE owner_uid IS NOT NULL
            GROUP BY owner_uid
            """
        ).fetchall()
        report_rows = conn.execute(
            """
            SELECT owner_uid, COUNT(*) AS report_count, MAX(updated_at) AS last_report_at
            FROM reports
            WHERE owner_uid IS NOT NULL
            GROUP BY owner_uid
            """
        ).fetchall()
        activity_rows = conn.execute(
            """
            SELECT
                owner_uid,
                MAX(owner_email) AS owner_email,
                COUNT(*) AS activity_count,
                MAX(created_at) AS last_activity_at,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_count,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_count,
                SUM(CASE WHEN status = 'started' THEN 1 ELSE 0 END) AS started_count
            FROM activity_logs
            WHERE owner_uid IS NOT NULL
            GROUP BY owner_uid
            """
        ).fetchall()

    uploads_by_uid = {row["owner_uid"]: dict(row) for row in upload_rows}
    reports_by_uid = {row["owner_uid"]: dict(row) for row in report_rows}
    activities_by_uid = {row["owner_uid"]: dict(row) for row in activity_rows}
    all_uids = set(uploads_by_uid) | set(reports_by_uid) | set(activities_by_uid)

    summaries: list[dict[str, Any]] = []
    for uid in all_uids:
        upload_row = uploads_by_uid.get(uid, {})
        report_row = reports_by_uid.get(uid, {})
        activity_row = activities_by_uid.get(uid, {})
        summaries.append(
            {
                "uid": uid,
                "email": activity_row.get("owner_email"),
                "upload_count": int(upload_row.get("upload_count") or 0),
                "report_count": int(report_row.get("report_count") or 0),
                "activity_count": int(activity_row.get("activity_count") or 0),
                "completed_count": int(activity_row.get("completed_count") or 0),
                "failed_count": int(activity_row.get("failed_count") or 0),
                "started_count": int(activity_row.get("started_count") or 0),
                "last_activity_at": activity_row.get("last_activity_at")
                or report_row.get("last_report_at")
                or upload_row.get("last_upload_at"),
            }
        )

    summaries.sort(key=lambda item: item.get("last_activity_at") or "", reverse=True)
    return summaries
