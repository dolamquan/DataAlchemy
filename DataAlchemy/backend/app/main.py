from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_health import router as health_router
from app.api.routes_projects import router as projects_router
from app.api.routes_reports import router as reports_router
from app.api.routes_supervisor import router as supervisor_router
from app.api.routes_upload import router as upload_router
from app.api.routes_ws import router as ws_router
from app.core.settings import CORS_ORIGINS
from app.db.models import init_upload_tables
import app.engine.agent_runtime  # noqa: F401 — registers real agent handlers on import

app = FastAPI(title="DataAlchemy API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(upload_router)
app.include_router(projects_router)
app.include_router(reports_router)
app.include_router(supervisor_router)
app.include_router(ws_router)


@app.on_event("startup")
def startup() -> None:
    init_upload_tables()


@app.get("/")
def root():
    return {"message": "DataAlchemy backend is running"}
