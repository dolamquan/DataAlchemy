from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import auth, credentials

from app.core.settings import (
    FIREBASE_PROJECT_ID,
    FIREBASE_SERVICE_ACCOUNT_JSON,
    FIREBASE_SERVICE_ACCOUNT_PATH,
)


class FirebaseAuthConfigurationError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_firebase_app() -> firebase_admin.App:
    if firebase_admin._apps:
        return firebase_admin.get_app()

    if FIREBASE_SERVICE_ACCOUNT_JSON:
        cert_payload = json.loads(FIREBASE_SERVICE_ACCOUNT_JSON)
        credential = credentials.Certificate(cert_payload)
    elif FIREBASE_SERVICE_ACCOUNT_PATH:
        credential = credentials.Certificate(Path(FIREBASE_SERVICE_ACCOUNT_PATH))
    else:
        raise FirebaseAuthConfigurationError(
            "Firebase Admin is not configured. Set FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_SERVICE_ACCOUNT_PATH."
        )

    options: dict[str, Any] = {}
    if FIREBASE_PROJECT_ID:
        options["projectId"] = FIREBASE_PROJECT_ID

    return firebase_admin.initialize_app(credential, options=options or None)


def verify_firebase_token(id_token: str) -> dict[str, Any]:
    app = get_firebase_app()
    return auth.verify_id_token(id_token, app=app, check_revoked=False)


def list_firebase_users() -> list[dict[str, Any]]:
    app = get_firebase_app()
    users: list[dict[str, Any]] = []
    page = auth.list_users(app=app)
    while page is not None:
        for user in page.users:
            users.append(
                {
                    "uid": user.uid,
                    "email": user.email,
                    "display_name": user.display_name,
                    "disabled": user.disabled,
                    "created_at": user.user_metadata.creation_timestamp,
                    "last_sign_in_at": user.user_metadata.last_sign_in_timestamp,
                    "custom_claims": user.custom_claims or {},
                }
            )
        page = page.get_next_page()
    return users
