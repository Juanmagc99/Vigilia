from uuid import UUID

from sqlmodel import Session

from app.db.models.alert import Alert


def save_alerts(session: Session, alerts: list[Alert]) -> list[Alert]:
    session.add_all(alerts)
    return alerts


def find_alert_by_id(session: Session, alert_id: UUID) -> Alert | None:
    return session.get(Alert, alert_id)
