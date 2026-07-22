from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.core.errors import DatabaseAppError
from app.core.logging import get_logger
from app.db.models.alert import Alert
from app.events.publisher import AlertEventPublisher
from app.repositories.alert_repository import save_alerts
from app.schemas.alerts import NormalizedAlert
from app.schemas.grafana import GrafanaWebhookPayload
from app.services.grafana_normalizer import normalize_grafana_payload


logger = get_logger(__name__)


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
    alerts = [
        _build_alert_from_normalized(normalized_alert)
        for normalized_alert in normalized_alerts
    ]

    try:
        saved_alerts = save_alerts(session, alerts)
        session.commit()

        for alert in saved_alerts:
            session.refresh(alert)

        logger.info(
            "Persisted alerts operation=ingest_grafana_payload entity=alert count=%s",
            len(saved_alerts),
        )
    except SQLAlchemyError as exc:
        session.rollback()
        raise DatabaseAppError(
            message="Could not save alerts",
            metadata={
                "operation": "ingest_grafana_payload",
                "entity": "alert",
                "count": len(normalized_alerts),
            },
        ) from exc

    for alert in saved_alerts:
        publisher.publish_alert_received(alert)

    return AlertIngestionResult(
        alerts_received=len(payload.alerts),
        alerts_normalized=len(normalized_alerts),
        alerts_persisted=len(saved_alerts),
        events_published=len(saved_alerts),
        saved_alerts=saved_alerts,
    )


def _build_alert_from_normalized(normalized_alert: NormalizedAlert) -> Alert:
    return Alert(
        source=normalized_alert.source,
        fingerprint=normalized_alert.fingerprint,
        status=normalized_alert.status,
        alert_name=normalized_alert.alert_name,
        service=normalized_alert.service,
        severity=normalized_alert.severity,
        summary=normalized_alert.summary,
        description=normalized_alert.description,
        labels=normalized_alert.labels,
        annotations=normalized_alert.annotations,
        starts_at=normalized_alert.starts_at,
        ends_at=normalized_alert.ends_at,
        received_at=normalized_alert.received_at,
        dashboard_url=normalized_alert.dashboard_url,
        panel_url=normalized_alert.panel_url,
        silence_url=normalized_alert.silence_url,
    )
