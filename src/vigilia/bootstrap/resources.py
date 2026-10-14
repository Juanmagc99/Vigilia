from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from vigilia.bootstrap.composition import (
    ApiApplication,
    ProcessResources,
    WorkerApplication,
    compose_api,
    compose_publisher,
    compose_worker,
)
from vigilia.bootstrap.settings import Settings


@asynccontextmanager
async def _resources[T: ProcessResources](
    settings: Settings, composer: Callable[[Settings], T]
) -> AsyncIterator[T]:
    application = composer(settings)
    try:
        yield application
    finally:
        try:
            if application.traffic_controls:
                await application.traffic_controls.close()
        finally:
            await application.engine.dispose()


def api_resources(settings: Settings) -> AbstractAsyncContextManager[ApiApplication]:
    return _resources(settings, compose_api)


def worker_resources(
    settings: Settings,
) -> AbstractAsyncContextManager[WorkerApplication]:
    return _resources(settings, compose_worker)


def publisher_resources(
    settings: Settings,
) -> AbstractAsyncContextManager[ProcessResources]:
    return _resources(settings, compose_publisher)
