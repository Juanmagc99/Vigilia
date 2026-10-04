import json
from pathlib import Path

from vigilia.adapters.grafana.normalizer import normalize_grafana_payload
from vigilia.adapters.grafana.schemas import GrafanaWebhookPayload


def test_normalizes_real_grafana_notification_test_payload() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "grafana_notification_test.json"
    payload_data = json.loads(fixture_path.read_text())
    payload = GrafanaWebhookPayload.model_validate(payload_data)

    alerts = normalize_grafana_payload(payload)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.source == "grafana"
    assert alert.fingerprint == "57c6d9296de2ad39"
    assert alert.alert_name == "TestAlert"
    assert alert.service == "Grafana"
    assert alert.summary == "Notification test"
    assert alert.status == "firing"
