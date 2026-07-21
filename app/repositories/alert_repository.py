from uuid import UUID

from sqlmodel import Session

from app.db.models.alert import Alert
from app.schemas.alerts import NormalizedAlert


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

    session.add_all(alerts)

    return alerts


def find_alert_by_id(session: Session, alert_id: UUID) -> Alert | None:
    return session.get(Alert, alert_id)
