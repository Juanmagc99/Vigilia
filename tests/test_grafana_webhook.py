import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_grafana_webhook_accepts_real_notification_test_payload() -> None:
    client = TestClient(app)
    fixture_path = Path(__file__).parent / "fixtures" / "grafana_notification_test.json"
    payload = json.loads(fixture_path.read_text())

    response = client.post("/webhooks/grafana", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "source": "grafana",
        "alerts_received": 1,
        "alerts_normalized": 1,
        "group_key": "webhook-57c6d9296de2ad39-1782063307",
    }
