from pathlib import Path
import uuid

from fastapi import HTTPException, UploadFile

from app.core.settings import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, UPLOAD_DIR


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