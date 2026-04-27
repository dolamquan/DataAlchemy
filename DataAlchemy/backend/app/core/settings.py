import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
ALLOWED_EXTENSIONS = {".csv"}

CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

def _env_value(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


OPENAI_API_KEY: str = _env_value("OPENAI_API_KEY")
OPENAI_MODEL: str = _env_value("OPENAI_MODEL", "gpt-4o") or "gpt-4o"

FIREBASE_PROJECT_ID: str = _env_value("FIREBASE_PROJECT_ID")
FIREBASE_SERVICE_ACCOUNT_PATH: str = _env_value("FIREBASE_SERVICE_ACCOUNT_PATH")
FIREBASE_SERVICE_ACCOUNT_JSON: str = _env_value("FIREBASE_SERVICE_ACCOUNT_JSON")
ADMIN_EMAILS: tuple[str, ...] = tuple(
    value.strip().lower() for value in _env_value("ADMIN_EMAILS").split(",") if value.strip()
)
ADMIN_UIDS: tuple[str, ...] = tuple(
    value.strip() for value in _env_value("ADMIN_UIDS").split(",") if value.strip()
)
LOG_FIREBASE_BEARER_TOKEN: bool = _env_flag("LOG_FIREBASE_BEARER_TOKEN", False)

print("LOG_FIREBASE_BEARER_TOKEN =", LOG_FIREBASE_BEARER_TOKEN, flush=True)