from fastapi import FastAPI

from app.api.exception_handlers import register_exception_handlers
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging


configure_logging()

app = FastAPI(
    title=settings.app_name,
    description="Alert ingestion and incident intelligence backend",
    version="0.1.0"
)

register_exception_handlers(app)
app.include_router(api_router)
