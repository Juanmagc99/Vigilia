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