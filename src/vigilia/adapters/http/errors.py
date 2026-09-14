from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from vigilia.application.errors import AppError
from vigilia.observability.logging import get_logger


logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "Application error code=%s path=%s metadata=%s",
        exc.code,
        request.url.path,
        exc.metadata,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": exc.error_type,
                "code": exc.code,
                "message": exc.message,
                "metadata": exc.metadata,
            }
        },
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "type": "validation_error",
                "code": "request_validation_failed",
                "message": "Request validation failed",
                "metadata": {"errors": exc.errors()},
            }
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "type": "internal_error",
                "code": "internal_server_error",
                "message": "Unexpected internal server error",
                "metadata": {},
            }
        },
    )
