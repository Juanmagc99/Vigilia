from typing import Any


class AppError(Exception):
    status_code: int = 500
    error_type: str = "app_error"
    default_code: str = "app_error"
    default_message: str = "Application error"

    def __init__(
        self,
        *,
        message: str | None = None,
        code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.metadata = metadata or {}
        super().__init__(self.message)


class ValidationAppError(AppError):
    status_code = 422
    error_type = "validation_error"
    default_code = "validation_error"
    default_message = "Validation error"


class DatabaseAppError(AppError):
    status_code = 500
    error_type = "database_error"
    default_code = "database_error"
    default_message = "Database error"


class ExternalServiceAppError(AppError):
    status_code = 502
    error_type = "external_service_error"
    default_code = "external_service_error"
    default_message = "External service error"


class NotFoundAppError(AppError):
    status_code = 404
    error_type = "not_found"
    default_code = "not_found"
    default_message = "Resource not found"


class ConflictAppError(AppError):
    status_code = 409
    error_type = "conflict"
    default_code = "conflict"
    default_message = "Resource conflict"


class InternalAppError(AppError):
    status_code = 500
    error_type = "internal_error"
    default_code = "internal_server_error"
    default_message = "Unexpected internal server error"
