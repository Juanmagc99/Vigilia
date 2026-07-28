import hashlib
import hmac
import time
from typing import Annotated

from fastapi import Header, Request

from app.core.config import settings
from app.core.errors import (
    AuthenticationAppError,
    SecurityConfigurationAppError,
)


async def verify_grafana_signature(
    request: Request,
    signature: Annotated[
        str | None,
        Header(alias="X-Grafana-Alerting-Signature"),
    ] = None,
    timestamp: Annotated[
        str | None,
        Header(alias="X-Grafana-Alerting-Timestamp"),
    ] = None,
) -> None:
    configured_secret = settings.grafana_webhook_hmac_secret

    if configured_secret is None:
        raise SecurityConfigurationAppError(
            code="grafana_webhook_security_not_configured",
        )

    if signature is None or timestamp is None:
        raise AuthenticationAppError(
            code="missing_grafana_signature",
        )

    try:
        timestamp_value = int(timestamp)
    except ValueError as exc:
        raise AuthenticationAppError(
            code="invalid_grafana_signature",
        ) from exc

    request_age = abs(int(time.time()) - timestamp_value)

    if request_age > settings.grafana_webhook_max_age_seconds:
        raise AuthenticationAppError(
            code="expired_grafana_signature",
        )

    raw_body = await request.body()

    signed_payload = (
        timestamp.encode("utf-8")
        + b":"
        + raw_body
    )

    expected_signature = hmac.new(
        key=configured_secret.get_secret_value().encode("utf-8"),
        msg=signed_payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        expected_signature,
        signature,
    ):
        raise AuthenticationAppError(
            code="invalid_grafana_signature",
        )

async def verify_api_token(
    authorization: Annotated[str | None, Header()] = None
) -> None:

    conf_token = settings.api_token

    if conf_token is None:
        raise SecurityConfigurationAppError(
            code="api_security_not_configured"
        )

    if authorization is None:
        raise AuthenticationAppError(
            code="missing_api_token"
        )

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        raise AuthenticationAppError(
            code="invalid_api_token",
        )

    if not hmac.compare_digest(
        conf_token.get_secret_value(),
        token,
    ):
        raise AuthenticationAppError(
            code="invalid_api_token",
        )