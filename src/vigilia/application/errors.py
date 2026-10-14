from typing import Any


class AppError(Exception):
    status_code = 500
    error_type = "app_error"
    default_code = "app_error"
    default_message = "Application error"

    def __init__(
        self,
        *,
        message: str | None = None,
        code: str | None = None,
        metadata: dict[str, Any] | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.metadata = metadata or {}
        self.retry_after_seconds = retry_after_seconds
        super().__init__(self.message)

    @property
    def headers(self) -> dict[str, str]:
        if self.retry_after_seconds is None:
            return {}
        return {"Retry-After": str(self.retry_after_seconds)}


class RateLimitAppError(AppError):
    status_code = 429
    error_type = "rate_limit_error"
    default_code = "rate_limit_exceeded"
    default_message = "Too many requests. Please try again later."


class RateLimitBackendUnavailableAppError(AppError):
    status_code = 503
    error_type = "service_unavailable"
    default_code = "rate_limit_backend_unavailable"
    default_message = "Request limits are temporarily unavailable"

    def __init__(self) -> None:
        super().__init__(retry_after_seconds=5)


class DatabaseAppError(AppError):
    error_type = "database_error"
    default_code = "database_error"
    default_message = "Database error"


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


class ValidationAppError(AppError):
    status_code = 422
    error_type = "validation_error"
    default_code = "invalid_request"
    default_message = "Request validation failed"


class FeatureUnavailableAppError(AppError):
    status_code = 503
    error_type = "feature_unavailable"
    default_code = "feature_disabled"
    default_message = "Feature is not enabled"


class AuthenticationAppError(AppError):
    status_code = 401
    error_type = "authentication_error"
    default_code = "authentication_failed"
    default_message = "Authentication failed"


class SecurityConfigurationAppError(AppError):
    status_code = 503
    error_type = "configuration_error"
    default_code = "security_not_configured"
    default_message = "Security is not configured"


class TransientInvestigationError(AppError):
    status_code = 503
    error_type = "investigation_error"
    default_code = "investigation_temporarily_unavailable"
    default_message = "Investigation could not be completed yet"


class PermanentInvestigationError(AppError):
    error_type = "investigation_error"
    default_code = "investigation_failed"
    default_message = "Investigation could not be completed"
