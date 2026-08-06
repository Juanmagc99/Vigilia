import copy

import pytest

from app.core.config import settings
from app.db.models.outbox_event import OutboxEvent
from app.db.session import get_session
from app.main import app


@pytest.fixture
def grafana_endpoint_dependencies(
    fake_session,
) -> tuple:
    def fake_get_session():
        yield fake_session

    app.dependency_overrides[get_session] = fake_get_session
    return (fake_session,)


def test_grafana_webhook_accepts_real_notification_test_payload(
    client,
    grafana_payload,
    configured_grafana_security,
    signed_grafana_request,
    grafana_endpoint_dependencies,
) -> None:
    (fake_session,) = grafana_endpoint_dependencies
    body, headers = signed_grafana_request(grafana_payload)

    response = client.post(
        "/webhooks/grafana",
        content=body,
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "source": "grafana",
        "alerts_received": 1,
        "alerts_normalized": 1,
        "alerts_persisted": 1,
        "events_queued": 1,
        "group_key": "webhook-57c6d9296de2ad39-1782063307",
    }
    assert fake_session.commit_called is True
    assert fake_session.rollback_called is False
    assert fake_session.refreshed == []
    assert len(fake_session.added) == 2
    assert isinstance(fake_session.added[1], OutboxEvent)
    assert fake_session.added[1].topic == settings.alerts_received_topic


@pytest.mark.parametrize(
    "missing_header",
    [
        "X-Grafana-Alerting-Signature",
        "X-Grafana-Alerting-Timestamp",
    ],
)
def test_grafana_webhook_rejects_missing_signature_headers(
    client,
    grafana_payload,
    configured_grafana_security,
    signed_grafana_request,
    grafana_endpoint_dependencies,
    missing_header,
) -> None:
    (fake_session,) = grafana_endpoint_dependencies
    body, headers = signed_grafana_request(grafana_payload)
    headers.pop(missing_header)

    response = client.post(
        "/webhooks/grafana",
        content=body,
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_grafana_signature"
    assert fake_session.commit_called is False
    assert fake_session.added == []


def test_grafana_webhook_rejects_invalid_signature(
    client,
    grafana_payload,
    configured_grafana_security,
    signed_grafana_request,
    grafana_endpoint_dependencies,
) -> None:
    (fake_session,) = grafana_endpoint_dependencies
    body, headers = signed_grafana_request(grafana_payload)
    headers["X-Grafana-Alerting-Signature"] = "0" * 64

    response = client.post(
        "/webhooks/grafana",
        content=body,
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_grafana_signature"
    assert fake_session.commit_called is False
    assert fake_session.added == []


def test_grafana_webhook_rejects_expired_signature(
    client,
    grafana_payload,
    configured_grafana_security,
    signed_grafana_request,
    grafana_endpoint_dependencies,
) -> None:
    (fake_session,) = grafana_endpoint_dependencies
    body, headers = signed_grafana_request(
        grafana_payload,
        timestamp="1749999699",
    )

    response = client.post(
        "/webhooks/grafana",
        content=body,
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "expired_grafana_signature"
    assert fake_session.commit_called is False
    assert fake_session.added == []


def test_grafana_webhook_rejects_body_altered_after_signing(
    client,
    grafana_payload,
    configured_grafana_security,
    signed_grafana_request,
    grafana_endpoint_dependencies,
) -> None:
    (fake_session,) = grafana_endpoint_dependencies
    original_body, _ = signed_grafana_request(grafana_payload)
    altered_payload = copy.deepcopy(grafana_payload)
    altered_payload["status"] = "resolved"
    body, headers = signed_grafana_request(
        altered_payload,
        body_to_sign=original_body,
    )

    response = client.post(
        "/webhooks/grafana",
        content=body,
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_grafana_signature"
    assert fake_session.commit_called is False
    assert fake_session.added == []


def test_grafana_webhook_returns_503_when_security_is_not_configured(
    client,
    grafana_payload,
    monkeypatch,
    signed_grafana_request,
) -> None:
    monkeypatch.setattr(settings, "grafana_webhook_hmac_secret", None)
    body, headers = signed_grafana_request(grafana_payload)

    response = client.post(
        "/webhooks/grafana",
        content=body,
        headers=headers,
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == (
        "grafana_webhook_security_not_configured"
    )
