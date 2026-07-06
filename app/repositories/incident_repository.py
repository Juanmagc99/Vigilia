from datetime import datetime
from uuid import UUID

from sqlmodel import Session, asc, desc, select

from app.db.models.alert import Alert
from app.db.models.incident import Incident
from app.db.models.incident_alert import IncidentAlert


def find_recent_open_incident_for_service(
    session: Session,
    service: str,
    since: datetime,
) -> Incident | None:
    statement = (
        select(Incident)
        .where(Incident.status == "open")
        .where(Incident.service == service)
        .where(Incident.updated_at >= since)
        .order_by(desc(Incident.updated_at))
    )

    return session.exec(statement).first()


def create_incident_from_alert(session: Session, alert: Alert) -> Incident:
    incident = Incident(
        status="open",
        service=alert.service,
        severity=alert.severity,
        title=alert.alert_name or alert.summary or f"Incident in {alert.service}",
        started_at=alert.starts_at,
        updated_at=alert.received_at,
    )

    session.add(incident)

    return incident


def attach_alert_to_incident(
    session: Session,
    incident: Incident,
    alert: Alert,
) -> None:
    existing_link = session.get(IncidentAlert, (incident.id, alert.id))

    if existing_link is not None:
        return

    link = IncidentAlert(
        incident_id=incident.id,
        alert_id=alert.id,
    )

    session.add(link)


def find_open_incident_by_fingerprint(
    session: Session,
    fingerprint: str,
) -> Incident | None:
    statement = (
        select(Incident)
        .join(IncidentAlert, IncidentAlert.incident_id == Incident.id) # type: ignore
        .join(Alert, Alert.id == IncidentAlert.alert_id) # type: ignore
        .where(Incident.status == "open")
        .where(Alert.fingerprint == fingerprint)
        .order_by(desc(Incident.updated_at))
    )

    return session.exec(statement).first()


def update_incident_activity(
    session: Session,
    incident: Incident,
    alert: Alert,
) -> Incident:
    incident.updated_at = alert.received_at

    if alert.severity != "unknown":
        incident.severity = alert.severity

    session.add(incident)

    return incident


def resolve_incident(
    session: Session,
    incident: Incident,
    resolved_at: datetime,
) -> Incident:
    incident.status = "resolved"
    incident.resolved_at = resolved_at
    incident.updated_at = resolved_at

    session.add(incident)

    return incident


def get_latest_alert_statuses_for_incident(
    session: Session,
    incident_id: UUID,
) -> dict[str, str]:
    statement = (
        select(Alert)
        .join(IncidentAlert, IncidentAlert.alert_id == Alert.id) # type: ignore
        .where(IncidentAlert.incident_id == incident_id)
        .order_by(asc(Alert.received_at))
    )

    alerts = session.exec(statement).all()

    latest_by_fingerprint: dict[str, str] = {}

    for alert in alerts:
        latest_by_fingerprint[alert.fingerprint] = alert.status

    return latest_by_fingerprint
