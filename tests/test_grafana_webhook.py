from app.db.session import get_session
from app.events.publisher import get_alert_event_publisher
from app.main import app


def test_grafana_webhook_accepts_real_notification_test_payload(
    client,
    grafana_payload,
    fake_session,
    fake_alert_publisher,
) -> None:
    def fake_get_session():
        yield fake_session

    app.dependency_overrides[get_session] = fake_get_session
    app.dependency_overrides[get_alert_event_publisher] = (
        lambda: fake_alert_publisher
    )

    response = client.post("/webhooks/grafana", json=grafana_payload)

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "source": "grafana",
        "alerts_received": 1,
        "alerts_normalized": 1,
        "alerts_persisted": 1,
        "events_published": 1,
        "group_key": "webhook-57c6d9296de2ad39-1782063307",
    }
    assert fake_session.commit_called is True
    assert fake_session.rollback_called is False
    assert len(fake_session.added) == 1
    assert len(fake_alert_publisher.published_alerts) == 1
    assert fake_alert_publisher.published_alerts[0].fingerprint == (
        "57c6d9296de2ad39"
    )
