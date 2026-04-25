from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, is_admin_identity, require_admin
from app.core.firebase_auth import list_firebase_users
from app.db.models import list_activity_logs, summarize_user_activity

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _iso_from_millis(value: int | None) -> str | None:
    if not value:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


@router.get("/access")
def admin_access(current_user: dict = Depends(get_current_user)) -> dict[str, bool]:
    return {"is_admin": bool(current_user.get("is_admin"))}


@router.get("/overview")
def admin_overview(current_user: dict = Depends(require_admin)) -> dict:
    firebase_users = list_firebase_users()
    activity_summary = summarize_user_activity()
    activity_by_uid = {row["uid"]: row for row in activity_summary}

    users: list[dict] = []
    for user in firebase_users:
        summary = activity_by_uid.get(user["uid"], {})
        last_activity = summary.get("last_activity_at") or _iso_from_millis(user.get("last_sign_in_at"))
        users.append(
            {
                "uid": user["uid"],
                "email": user.get("email"),
                "display_name": user.get("display_name"),
                "status": "disabled" if user.get("disabled") else "active",
                "is_admin": is_admin_identity(
                    uid=user["uid"],
                    email=user.get("email"),
                    claims=user.get("custom_claims"),
                ),
                "created_at": _iso_from_millis(user.get("created_at")),
                "last_sign_in_at": _iso_from_millis(user.get("last_sign_in_at")),
                "last_activity_at": last_activity,
                "upload_count": int(summary.get("upload_count") or 0),
                "report_count": int(summary.get("report_count") or 0),
                "activity_count": int(summary.get("activity_count") or 0),
                "completed_count": int(summary.get("completed_count") or 0),
                "failed_count": int(summary.get("failed_count") or 0),
            }
        )

    users.sort(key=lambda item: item.get("last_activity_at") or "", reverse=True)
    activities = list_activity_logs(limit=250)

    totals = {
        "total_users": len(users),
        "active_users": sum(1 for user in users if user["status"] == "active"),
        "total_uploads": sum(int(user["upload_count"]) for user in users),
        "total_reports": sum(int(user["report_count"]) for user in users),
        "total_activities": sum(int(user["activity_count"]) for user in users),
        "failed_activities": sum(int(user["failed_count"]) for user in users),
    }

    return {
        "totals": totals,
        "users": users,
        "activities": activities,
    }
