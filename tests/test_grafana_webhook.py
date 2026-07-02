import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app


@pytest.mark.skip(reason="Webhook flow is evolving while persistence/events are wired")
def test_grafana_webhook_accepts_real_notification_test_payload(monkeypatch) -> None:
    client = TestClient(app)
    fixture_path = Path(__file__).parent / "fixtures" / "grafana_notification_test.json"
    payload = json.loads(fixture_path.read_text())

    def fake_get_session():
        yield object()

    def fake_save_alerts(session, normalized_alerts):
        return normalized_alerts

    app.dependency_overrides[get_session] = fake_get_session
    monkeypatch.setattr(
        "app.api.routes.grafana_handler.save_alerts", fake_save_alerts
    )

    response = client.post("/webhooks/grafana", json=payload)

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "source": "grafana",
        "alerts_received": 1,
        "alerts_normalized": 1,
        "alerts_persisted": 1,
        "group_key": "webhook-57c6d9296de2ad39-1782063307",
    }
