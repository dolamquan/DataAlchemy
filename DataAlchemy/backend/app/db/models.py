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
				dataset_id TEXT NOT NULL UNIQUE,
				file_id TEXT NOT NULL,
				content_json TEXT NOT NULL,
				created_at TEXT NOT NULL,
				updated_at TEXT NOT NULL
			)
			"""
		)
		columns = {
			row["name"]
			for row in conn.execute("PRAGMA table_info(uploads)").fetchall()
		}
		if "file_content" not in columns:
			conn.execute("ALTER TABLE uploads ADD COLUMN file_content BLOB")
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


def create_upload_record(
	*,
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
				file_id,
				original_filename,
				stored_path,
				file_size_bytes,
				schema_profile_json,
				file_content,
				created_at
			) VALUES (?, ?, ?, ?, ?, ?, ?)
			""",
			(
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


def list_recent_upload_records(limit: int = 10, *, available_only: bool = True) -> list[dict[str, Any]]:
	safe_limit = max(1, min(limit, 100))

	with get_connection() as conn:
		rows = conn.execute(
			"""
			SELECT file_id, original_filename, stored_path, file_size_bytes, created_at, file_content
			FROM uploads
			ORDER BY datetime(created_at) DESC
			LIMIT ?
			""",
			(max(safe_limit * 3, safe_limit),),
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


def get_upload_file_content_by_file_id(file_id: str) -> bytes | None:
	"""Return stored CSV bytes for a file_id, or None for old records without content."""
	with get_connection() as conn:
		row = conn.execute(
			"""
			SELECT file_content
			FROM uploads
			WHERE file_id = ?
			""",
			(file_id,),
		).fetchone()

	if row is None:
		return None

	content = row["file_content"]
	return bytes(content) if content is not None else None


def save_report_record(
	*,
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
				dataset_id,
				file_id,
				content_json,
				created_at,
				updated_at
			) VALUES (?, ?, ?, ?, ?)
			ON CONFLICT(dataset_id) DO UPDATE SET
				file_id = excluded.file_id,
				content_json = excluded.content_json,
				updated_at = excluded.updated_at
			""",
			(
				dataset_id,
				file_id,
				payload,
				timestamp,
				timestamp,
			),
		)
		conn.commit()


def get_report_record_by_dataset_id(dataset_id: str) -> dict[str, Any] | None:
	init_upload_tables()
	with get_connection() as conn:
		row = conn.execute(
			"""
			SELECT dataset_id, file_id, content_json, created_at, updated_at
			FROM reports
			WHERE dataset_id = ?
			""",
			(dataset_id,),
		).fetchone()

	if row is None:
		return None

	return {
		"dataset_id": row["dataset_id"],
		"file_id": row["file_id"],
		"content": json.loads(row["content_json"]),
		"created_at": row["created_at"],
		"updated_at": row["updated_at"],
	}
