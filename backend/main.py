"""FastAPI entrypoint for AgriVision AI."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.api import agent, alerts, auth, crops, dashboard, diagnoses, farms, livestock
from backend.core.config import get_settings
from backend.db.database import SessionLocal, init_db
from backend.services.crop_inference import model_status


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    model_status()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", description="Unified local-first crop and livestock health platform", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"])

for router in (auth.router, farms.router, crops.router, diagnoses.router, livestock.router, alerts.router, dashboard.router, agent.router):
    app.include_router(router)


@app.get("/health", tags=["System"])
def health():
    database = "disconnected"
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        database = "connected"
    except Exception:
        pass
    status = model_status()
    return {"status": "ok" if database == "connected" else "degraded", "model_loaded": status["loaded"], "mock_mode": status["mock_mode"], "database": database}


@app.get("/", include_in_schema=False)
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/health"}
