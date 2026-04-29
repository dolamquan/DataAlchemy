from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException, WebSocket
from firebase_admin import exceptions as firebase_exceptions

from app.core.firebase_auth import FirebaseAuthConfigurationError, verify_firebase_token
from app.core.settings import ADMIN_EMAILS, ADMIN_UIDS, LOG_FIREBASE_BEARER_TOKEN


def decode_auth_token(token: str) -> dict[str, Any]:
    try:
        return verify_firebase_token(token)
    except FirebaseAuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, firebase_exceptions.FirebaseError) as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from exc


def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    _log_bearer_token(token, source="http")

    decoded = decode_auth_token(token)
    return {
        "uid": str(decoded["uid"]),
        "email": decoded.get("email"),
        "name": decoded.get("name"),
        "is_admin": _is_admin(decoded),
        "claims": decoded,
    }


def get_optional_user(authorization: str | None = Header(default=None)) -> dict[str, Any] | None:
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    _log_bearer_token(token, source="http")

    decoded = decode_auth_token(token)
    return {
        "uid": str(decoded["uid"]),
        "email": decoded.get("email"),
        "name": decoded.get("name"),
        "is_admin": _is_admin(decoded),
        "claims": decoded,
    }


async def authenticate_websocket(websocket: WebSocket) -> dict[str, Any]:
    token = websocket.query_params.get("token", "").strip()
    if not token:
        await websocket.close(code=4401, reason="Missing auth token")
        raise HTTPException(status_code=401, detail="Missing auth token")
    _log_bearer_token(token, source="websocket")

    decoded = decode_auth_token(token)
    return {
        "uid": str(decoded["uid"]),
        "email": decoded.get("email"),
        "name": decoded.get("name"),
        "is_admin": _is_admin(decoded),
        "claims": decoded,
    }


def _is_admin(decoded: dict[str, Any]) -> bool:
    claims = decoded.get("claims") if isinstance(decoded.get("claims"), dict) else decoded
    email = str(claims.get("email") or "").strip().lower()
    uid = str(claims.get("uid") or "").strip()
    if bool(claims.get("admin")):
        return True
    if uid and uid in ADMIN_UIDS:
        return True
    if email and email in ADMIN_EMAILS:
        return True
    return False


def is_admin_identity(*, uid: str | None, email: str | None, claims: dict[str, Any] | None = None) -> bool:
    if claims and bool(claims.get("admin")):
        return True
    if uid and uid in ADMIN_UIDS:
        return True
    if email and email.strip().lower() in ADMIN_EMAILS:
        return True
    return False


def _log_bearer_token(token: str, *, source: str) -> None:
    if not LOG_FIREBASE_BEARER_TOKEN:
        return
    print(f"[firebase] {source} bearer token: {token}", flush=True)


def require_admin(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
