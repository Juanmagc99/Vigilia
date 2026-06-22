from fastapi import FastAPI
from app.core.config import settings
from app.api.router import api_router

app = FastAPI(
    title=settings.app_name,
    description="Alert ingestion and incident intelligence backend",
    version="0.1.0"
)

app.include_router(api_router)