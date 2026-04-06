from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.schema_profiler import profile_csv
from app.services.storage import save_upload

router = APIRouter(prefix="/api", tags=["upload"])


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