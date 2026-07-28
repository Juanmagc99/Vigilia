from uuid import uuid4

import pytest

from app.core.config import settings


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/incidents"),
        ("get", f"/incidents/{uuid4()}"),
        ("get", f"/incidents/{uuid4()}/reports"),
        ("post", f"/incidents/{uuid4()}/report"),
    ],
)
def test_incident_endpoints_require_api_token(
    client,
    configured_api_security,
    method,
    path,
) -> None:
    response = getattr(client, method)(path)

    assert response.status_code == 401
    assert response.json()["error"] == {
        "type": "authentication_error",
        "code": "missing_api_token",
        "message": "Authentication failed",
        "metadata": {},
    }


@pytest.mark.parametrize(
    "authorization",
    [
        "Basic credentials",
        "Bearer",
        "Bearer invalid-token",
    ],
)
def test_incident_endpoints_reject_invalid_api_token(
    client,
    configured_api_security,
    authorization,
) -> None:
    response = client.get(
        "/incidents",
        headers={"Authorization": authorization},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_token"


def test_incident_endpoints_return_503_when_api_security_is_not_configured(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "api_token", None)

    response = client.get(
        "/incidents",
        headers={"Authorization": "Bearer any-token"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "api_security_not_configured"
