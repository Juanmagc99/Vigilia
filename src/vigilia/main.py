import argparse
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from vigilia import __version__
from vigilia.adapters.http.errors import register_exception_handlers
from vigilia.adapters.http.routes import router
from vigilia.bootstrap.resources import api_resources
from vigilia.bootstrap.settings import Settings
from vigilia.observability.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with api_resources(configured) as application:
            app.state.vigilia = application
            yield

    app = FastAPI(
        title=configured.app_name,
        description="Alert ingestion and incident investigation backend",
        version=__version__,
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.include_router(router)
    app.mount(
        "/ui",
        StaticFiles(
            directory=Path(__file__).parent / "adapters" / "http" / "ui",
            html=True,
        ),
        name="ui",
    )
    return app


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    configure_logging()
    uvicorn.run(
        "vigilia.main:create_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
        reload=args.reload,
    )
