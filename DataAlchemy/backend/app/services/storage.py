from pathlib import Path
import uuid

from fastapi import HTTPException, UploadFile

from app.core.settings import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, UPLOAD_DIR
from app.db.models import get_upload_file_content_by_file_id, get_upload_stored_path_by_file_id


CHUNK_SIZE = 1024 * 1024  # 1 MB


def validate_upload_file(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file name provided.")

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )


def generate_stored_filename(original_filename: str) -> str:
    extension = Path(original_filename).suffix.lower() or ".csv"
    return f"{uuid.uuid4().hex}{extension}"


def get_upload_path(file_id: str) -> Path:
    """Return the absolute Path to the uploaded file given its file_id (stored filename).

    Raises FileNotFoundError if the file does not exist on disk.
    """
    path = UPLOAD_DIR / file_id
    if not path.exists():
        raise FileNotFoundError(f"Upload file not found on disk: {path}")
    return path


def resolve_upload_path_from_db(file_id: str) -> Path:
    """Return an upload path, restoring the file from DB content if needed."""
    stored_path = get_upload_stored_path_by_file_id(file_id)
    candidates = []
    if stored_path:
        candidates.append(Path(stored_path))
    candidates.append(UPLOAD_DIR / file_id)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate

    content = get_upload_file_content_by_file_id(file_id)
    if content is None:
        missing_path = Path(stored_path) if stored_path else UPLOAD_DIR / file_id
        raise FileNotFoundError(f"Upload file not found on disk or in DB: {missing_path}")

    restore_path = Path(stored_path) if stored_path else UPLOAD_DIR / file_id
    restore_path.parent.mkdir(parents=True, exist_ok=True)
    restore_path.write_bytes(content)
    return restore_path


def save_upload(file: UploadFile) -> dict:
    """
    Save uploaded file to disk in chunks with size enforcement.

    Returns:
        {
            "path": str,
            "filename": str,
            "stored_name": str,
            "size": int
        }
    """
    validate_upload_file(file)

    stored_name = generate_stored_filename(file.filename)
    destination = UPLOAD_DIR / stored_name
    size = 0

    try:
        with destination.open("wb") as output:
            while True:
                chunk = file.file.read(CHUNK_SIZE)
                if not chunk:
                    break

                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum size of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
                    )

                output.write(chunk)

        return {
            "path": str(destination),
            "filename": file.filename,
            "stored_name": stored_name,
            "size": size,
        }

    except HTTPException:
        if destination.exists():
            destination.unlink(missing_ok=True)
        raise
    except Exception as exc:
        if destination.exists():
            destination.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {str(exc)}") from exc
    finally:
        try:
            file.file.close()
        except Exception:
            pass
