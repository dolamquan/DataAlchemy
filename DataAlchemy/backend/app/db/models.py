import json
from datetime import datetime, timezone
from typing import Any

from app.db.session import get_connection


def init_upload_tables() -> None:
	with get_connection() as conn:
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS uploads (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				file_id TEXT NOT NULL UNIQUE,
				original_filename TEXT NOT NULL,
				stored_path TEXT NOT NULL,
				file_size_bytes INTEGER NOT NULL,
				schema_profile_json TEXT NOT NULL,
				created_at TEXT NOT NULL
			)
			"""
		)
		conn.commit()


def create_upload_record(
	*,
	file_id: str,
	original_filename: str,
	stored_path: str,
	file_size_bytes: int,
	schema_profile: dict[str, Any],
) -> None:
	payload = json.dumps(schema_profile)
	created_at = datetime.now(timezone.utc).isoformat()

	with get_connection() as conn:
		conn.execute(
			"""
			INSERT INTO uploads (
				file_id,
				original_filename,
				stored_path,
				file_size_bytes,
				schema_profile_json,
				created_at
			) VALUES (?, ?, ?, ?, ?, ?)
			""",
			(
				file_id,
				original_filename,
				stored_path,
				file_size_bytes,
				payload,
				created_at,
			),
		)
		conn.commit()


def list_recent_upload_records(limit: int = 10) -> list[dict[str, Any]]:
	safe_limit = max(1, min(limit, 100))

	with get_connection() as conn:
		rows = conn.execute(
			"""
			SELECT file_id, original_filename, file_size_bytes, created_at
			FROM uploads
			ORDER BY datetime(created_at) DESC
			LIMIT ?
			""",
			(safe_limit,),
		).fetchall()

	return [dict(row) for row in rows]


def get_upload_schema_by_file_id(file_id: str) -> dict[str, Any] | None:
	with get_connection() as conn:
		row = conn.execute(
			"""
			SELECT schema_profile_json
			FROM uploads
			WHERE file_id = ?
			""",
			(file_id,),
		).fetchone()

	if row is None:
		return None

	return json.loads(row["schema_profile_json"])


def get_upload_record_by_file_id(file_id: str) -> dict[str, Any] | None:
	with get_connection() as conn:
		row = conn.execute(
			"""
			SELECT file_id, original_filename, file_size_bytes, created_at
			FROM uploads
			WHERE file_id = ?
			""",
			(file_id,),
		).fetchone()

	if row is None:
		return None

	return dict(row)


def get_upload_stored_path_by_file_id(file_id: str) -> str | None:
	"""Return the on-disk stored_path for a given file_id, or None if not found."""
	with get_connection() as conn:
		row = conn.execute(
			"""
			SELECT stored_path
			FROM uploads
			WHERE file_id = ?
			""",
			(file_id,),
		).fetchone()

	if row is None:
		return None

	return row["stored_path"]
