from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from vigilia.adapters.http.dependencies import ApplicationDependency
from vigilia.adapters.http.errors import app_error_handler
from vigilia.application.errors import AppError, RateLimitAppError

PROTECTED_ROOTS = {"alerts", "incidents", "investigations", "knowledge"}


async def _enforce(
    application, request: Request, bucket: str, subject: str, limit: int
):
    decision = await application.traffic_controls.check_rate(bucket, subject, limit)
    request.state.rate_limit_headers = decision.headers
    if not decision.allowed:
        raise RateLimitAppError(
            metadata={"bucket": bucket, "limit": limit},
            retry_after_seconds=decision.retry_after_seconds,
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        application = request.app.state.vigilia
        root = request.url.path.strip("/").split("/", 1)[0]
        protected = root in PROTECTED_ROOTS or request.url.path == "/webhooks/grafana"
        try:
            if application.settings.rate_limit_enabled and protected:
                await _enforce(
                    application,
                    request,
                    "ingress",
                    request.client.host if request.client else "unknown",
                    application.settings.rate_limit_ingress_per_minute,
                )
            response = await call_next(request)
        except AppError as exc:
            response = await app_error_handler(request, exc)
        response.headers.update(getattr(request.state, "rate_limit_headers", {}))
        return response


async def enforce_api_rate_limit(
    request: Request, response: Response, application: ApplicationDependency
) -> None:
    settings = application.settings
    if not settings.rate_limit_enabled:
        return
    subject = settings.api_token.get_secret_value()
    await _enforce(
        application, request, "api", subject, settings.rate_limit_api_per_minute
    )
    if request.method == "POST":
        route = request.scope["route"].path
        if route == "/incidents/{incident_id}/investigations":
            await _enforce(
                application,
                request,
                "investigations",
                subject,
                settings.rate_limit_investigations_per_minute,
            )
        elif route == "/knowledge/documents":
            await _enforce(
                application,
                request,
                "knowledge",
                subject,
                settings.rate_limit_knowledge_per_minute,
            )
    response.headers.update(request.state.rate_limit_headers)


async def enforce_webhook_rate_limit(
    request: Request, response: Response, application: ApplicationDependency
) -> None:
    if not application.settings.rate_limit_enabled:
        return
    await _enforce(
        application,
        request,
        "webhooks",
        "grafana",
        application.settings.rate_limit_webhooks_per_minute,
    )
    response.headers.update(request.state.rate_limit_headers)
