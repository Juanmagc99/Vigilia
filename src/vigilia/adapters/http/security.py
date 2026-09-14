import hashlib
import hmac
import time
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from vigilia.adapters.http.dependencies import ApplicationDependency
from vigilia.application.errors import (
    AuthenticationAppError,
    SecurityConfigurationAppError,
)

api_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="Vigilia API token",
    description="Bearer token configured through VIGILIA_API_TOKEN.",
)


async def verify_grafana_signature(
    request: Request,
    application: ApplicationDependency,
    signature: Annotated[
        str | None, Header(alias="X-Grafana-Alerting-Signature")
    ] = None,
    timestamp: Annotated[
        str | None, Header(alias="X-Grafana-Alerting-Timestamp")
    ] = None,
) -> None:
    configured_secret = application.settings.grafana_webhook_hmac_secret
    if configured_secret is None:
        raise SecurityConfigurationAppError(
            code="grafana_webhook_security_not_configured"
        )
    if signature is None or timestamp is None:
        raise AuthenticationAppError(code="missing_grafana_signature")
    try:
        timestamp_value = int(timestamp)
    except ValueError as exc:
        raise AuthenticationAppError(code="invalid_grafana_signature") from exc
    if (
        abs(int(time.time()) - timestamp_value)
        > application.settings.grafana_webhook_max_age_seconds
    ):
        raise AuthenticationAppError(code="expired_grafana_signature")
    signed_payload = timestamp.encode() + b":" + await request.body()
    expected = hmac.new(
        configured_secret.get_secret_value().encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise AuthenticationAppError(code="invalid_grafana_signature")


async def verify_api_token(
    application: ApplicationDependency,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(api_bearer)
    ] = None,
) -> None:
    configured_token = application.settings.api_token
    if configured_token is None:
        raise SecurityConfigurationAppError(code="api_security_not_configured")
    if credentials is None:
        raise AuthenticationAppError(code="missing_api_token")
    if credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise AuthenticationAppError(code="invalid_api_token")
    if not hmac.compare_digest(
        configured_token.get_secret_value(), credentials.credentials
    ):
        raise AuthenticationAppError(code="invalid_api_token")
