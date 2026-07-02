from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.core.errors import DatabaseAppError
from app.core.logging import get_logger
from app.db.models.alert import Alert
from app.schemas.alerts import NormalizedAlert


logger = get_logger(__name__)


def alert_from_normalized(normalized: NormalizedAlert) -> Alert:
    return Alert(
        source=normalized.source,
        fingerprint=normalized.fingerprint,
        status=normalized.status,
        alert_name=normalized.alert_name,
        service=normalized.service,
        severity=normalized.severity,
        summary=normalized.summary,
        description=normalized.description,
        labels=normalized.labels,
        annotations=normalized.annotations,
        starts_at=normalized.starts_at,
        ends_at=normalized.ends_at,
        received_at=normalized.received_at,
        dashboard_url=normalized.dashboard_url,
        panel_url=normalized.panel_url,
        silence_url=normalized.silence_url,
    )


def save_alerts(
    session: Session, normalized_alerts: list[NormalizedAlert]
) -> list[Alert]:
    alerts = [alert_from_normalized(alert) for alert in normalized_alerts]

    try:
        session.add_all(alerts)
        session.commit()

        for alert in alerts:
            session.refresh(alert)

        logger.info(
            "Persisted alerts operation=save_alerts entity=alert count=%s",
            len(alerts),
        )
        return alerts
    except SQLAlchemyError as exc:
        session.rollback()
        raise DatabaseAppError(
            message="Could not save alerts",
            metadata={
                "operation": "save_alerts",
                "entity": "alert",
                "count": len(alerts),
            },
        ) from exc
