from dataclasses import dataclass

from sqlmodel import Session

from app.db.models.alert import Alert
from app.events.publisher import AlertEventPublisher
from app.repositories.alert_repository import save_alerts
from app.schemas.grafana import GrafanaWebhookPayload
from app.services.grafana_normalizer import normalize_grafana_payload


@dataclass
class AlertIngestionResult:
    alerts_received: int
    alerts_normalized: int
    alerts_persisted: int
    events_published: int
    saved_alerts: list[Alert]


def ingest_grafana_payload(
    payload: GrafanaWebhookPayload,
    session: Session,
    publisher: AlertEventPublisher,
) -> AlertIngestionResult:
    normalized_alerts = normalize_grafana_payload(payload)
    saved_alerts = save_alerts(session, normalized_alerts)

    for alert in saved_alerts:
        publisher.publish_alert_received(alert)

    return AlertIngestionResult(
        alerts_received=len(payload.alerts),
        alerts_normalized=len(normalized_alerts),
        alerts_persisted=len(saved_alerts),
        events_published=len(saved_alerts),
        saved_alerts=saved_alerts,
    )