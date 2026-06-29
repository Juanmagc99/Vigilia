from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import AppError
from app.core.logging import get_logger


logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "Application error type=%s code=%s path=%s",
        exc.error_type,
        exc.code,
        request.url.path,
        extra={
            "error_type": exc.error_type,
            "error_code": exc.code,
            "path": request.url.path,
        },
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


async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.warning(
        "Request validation failed type=validation_error code=request_validation_failed path=%s",
        request.url.path,
        extra={
            "error_type": "validation_error",
            "error_code": "request_validation_failed",
            "path": request.url.path,
        },
    )
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


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled exception type=internal_error code=internal_server_error path=%s",
        request.url.path,
        extra={
            "error_type": "internal_error",
            "error_code": "internal_server_error",
            "path": request.url.path,
        },
    )
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
