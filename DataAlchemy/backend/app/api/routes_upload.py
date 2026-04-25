from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import decode_auth_token, get_current_user, get_optional_user
from app.core.settings import UPLOAD_DIR
from app.db.models import (
    create_upload_record,
    get_upload_schema_by_file_id,
    list_recent_upload_records,
    log_user_activity,
    user_can_access_artifact,
)
from app.services.schema_profiler import build_schema_insights, profile_csv
from app.services.storage import save_upload

router = APIRouter(prefix="/api", tags=["upload"])


@router.get("/uploads/recent")
def recent_uploads(
    limit: int = Query(default=50, ge=1, le=100),
    available_only: bool = Query(default=True),
    current_user: dict = Depends(get_current_user),
):
    return {
        "items": list_recent_upload_records(limit=limit, owner_uid=current_user["uid"], available_only=available_only)
    }


@router.get("/uploads/{file_id}/schema")
def upload_schema(file_id: str, current_user: dict = Depends(get_current_user)):
    schema = get_upload_schema_by_file_id(file_id, owner_uid=current_user["uid"])
    if schema is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    return {"file_id": file_id, "schema_profile": schema}


@router.get("/uploads/{file_id}/insights")
def upload_insights(file_id: str, top_n: int = Query(default=8, ge=1, le=25), current_user: dict = Depends(get_current_user)):
    schema = get_upload_schema_by_file_id(file_id, owner_uid=current_user["uid"])
    if schema is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    return {
        "file_id": file_id,
        "insights": build_schema_insights(schema_profile=schema, top_n=top_n),
    }


@router.get("/artifacts/{file_id}")
def download_artifact(
    file_id: str,
    token: str | None = Query(default=None),
    current_user: dict | None = Depends(get_optional_user),
):
    if "/" in file_id or "\\" in file_id or ".." in file_id:
        raise HTTPException(status_code=400, detail="Invalid file_id")
    resolved_user = current_user
    if resolved_user is None and token:
        decoded = decode_auth_token(token)
        resolved_user = {
            "uid": str(decoded["uid"]),
            "email": decoded.get("email"),
            "name": decoded.get("name"),
        }
    if resolved_user is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if not user_can_access_artifact(file_id, owner_uid=resolved_user["uid"]):
        raise HTTPException(status_code=404, detail="Artifact not found")
    path = (UPLOAD_DIR / file_id).resolve()
    upload_dir_resolved = UPLOAD_DIR.resolve()
    if not str(path).startswith(str(upload_dir_resolved)):
        raise HTTPException(status_code=400, detail="Invalid file_id")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path, filename=file_id, media_type="application/octet-stream")


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """
    Upload a CSV file, save it, profile its schema, and return JSON.
    """
    saved = save_upload(file)

    try:
        schema_profile = profile_csv(saved["path"], sample_rows=500, preview_rows_count=5)
        schema_profile["file_name"] = saved["filename"]
        schema_profile["stored_file_name"] = saved["stored_name"]
        schema_profile["file_size_bytes"] = saved["size"]

        create_upload_record(
            owner_uid=current_user["uid"],
            file_id=saved["stored_name"],
            original_filename=saved["filename"],
            stored_path=saved["path"],
            file_size_bytes=saved["size"],
            schema_profile=schema_profile,
            file_content=UPLOAD_DIR.joinpath(saved["stored_name"]).read_bytes(),
        )
        log_user_activity(
            owner_uid=current_user["uid"],
            owner_email=current_user.get("email"),
            activity_type="upload_csv",
            status="completed",
            resource_id=saved["stored_name"],
            resource_name=saved["filename"],
            details={"file_size_bytes": saved["size"]},
        )

        return {
            "message": "Upload successful",
            "file_id": saved["stored_name"],
            "schema_profile": schema_profile,
        }

    except ValueError as exc:
        log_user_activity(
            owner_uid=current_user["uid"],
            owner_email=current_user.get("email"),
            activity_type="upload_csv",
            status="failed",
            resource_name=file.filename,
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        log_user_activity(
            owner_uid=current_user["uid"],
            owner_email=current_user.get("email"),
            activity_type="upload_csv",
            status="failed",
            resource_name=file.filename,
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=500, detail=f"Failed to profile CSV: {str(exc)}") from exc
