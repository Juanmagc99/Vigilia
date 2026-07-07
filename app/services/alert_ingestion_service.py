from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.core.errors import DatabaseAppError
from app.core.logging import get_logger
from app.db.models.alert import Alert
from app.events.publisher import AlertEventPublisher
from app.repositories.alert_repository import save_alerts
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

    try:
        saved_alerts = save_alerts(session, normalized_alerts)
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
