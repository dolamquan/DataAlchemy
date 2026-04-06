from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_health import router as health_router
from app.api.routes_upload import router as upload_router
from app.core.settings import CORS_ORIGINS

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


@app.get("/")
def root():
    return {"message": "DataAlchemy backend is running"}