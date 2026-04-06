from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.db.models import create_upload_record, get_upload_schema_by_file_id, list_recent_upload_records
from app.services.schema_profiler import build_schema_insights, profile_csv
from app.services.storage import save_upload

router = APIRouter(prefix="/api", tags=["upload"])


@router.get("/uploads/recent")
def recent_uploads(limit: int = Query(default=50, ge=1, le=100)):
    return {"items": list_recent_upload_records(limit=limit)}


@router.get("/uploads/{file_id}/schema")
def upload_schema(file_id: str):
    schema = get_upload_schema_by_file_id(file_id)
    if schema is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    return {"file_id": file_id, "schema_profile": schema}


@router.get("/uploads/{file_id}/insights")
def upload_insights(file_id: str, top_n: int = Query(default=8, ge=1, le=25)):
    schema = get_upload_schema_by_file_id(file_id)
    if schema is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    return {
        "file_id": file_id,
        "insights": build_schema_insights(schema_profile=schema, top_n=top_n),
    }


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
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
            file_id=saved["stored_name"],
            original_filename=saved["filename"],
            stored_path=saved["path"],
            file_size_bytes=saved["size"],
            schema_profile=schema_profile,
        )

        return {
            "message": "Upload successful",
            "file_id": saved["stored_name"],
            "schema_profile": schema_profile,
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to profile CSV: {str(exc)}") from exc