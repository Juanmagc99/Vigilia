from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.exception_handlers import register_exception_handlers
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.services.llm_client import LLMClient
from app.services.prompt_renderer import PromptRenderer
from app.services.report_generation_service import ReportGenerationService


configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.llm_api_key is not None and settings.llm_model is not None:
        prompt_renderer = PromptRenderer(
            templates_dir=Path(__file__).resolve().parent / "prompts",
        )
        llm_client = LLMClient(
            model=settings.llm_model,
            api_key=settings.llm_api_key.get_secret_value(),
            timeout_seconds=settings.llm_timeout_seconds,
        )
        app.state.report_generation_service = ReportGenerationService(
            prompt_renderer=prompt_renderer,
            llm_client=llm_client,
        )
    else:
        app.state.report_generation_service = None

    yield

app = FastAPI(
    title=settings.app_name,
    description="Alert ingestion and incident intelligence backend",
    version="0.1.0",
    lifespan=lifespan,
)

register_exception_handlers(app)
app.include_router(api_router)
