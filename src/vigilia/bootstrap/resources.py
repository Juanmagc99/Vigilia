from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import TypeVar

from vigilia.bootstrap.composition import (
    ApiApplication,
    ProcessResources,
    WorkerApplication,
    compose_api,
    compose_publisher,
    compose_worker,
)
from vigilia.bootstrap.settings import Settings


T = TypeVar("T", bound=ProcessResources)


@asynccontextmanager
async def _resources(
    settings: Settings, composer: Callable[[Settings], T]
) -> AsyncIterator[T]:
    application = composer(settings)
    try:
        yield application
    finally:
        await application.engine.dispose()


def api_resources(settings: Settings):
    return _resources(settings, compose_api)


def worker_resources(settings: Settings):
    return _resources(settings, compose_worker)


def publisher_resources(settings: Settings):
    return _resources(settings, compose_publisher)
