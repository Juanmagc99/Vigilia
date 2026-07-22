from datetime import datetime
from uuid import UUID

from sqlmodel import Session, asc, desc, select

from app.db.models.alert import Alert
from app.db.models.incident import Incident
from app.db.models.incident_alert import IncidentAlert


SEVERITY_RANK = {
    "unknown": 0,
    "info": 1,
    "warning": 2,
    "critical": 3,
}


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

    incident.severity = _highest_severity(
        current=incident.severity,
        incoming=alert.severity,
    )

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


def find_latest_alert_statuses_by_incident_id(
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


def find_all_incidents(session: Session) -> list[Incident]:
    statement = select(Incident).order_by(desc(Incident.updated_at))
    return list(session.exec(statement).all())

def find_incident_by_id(
    session: Session,
    incident_id: UUID
) -> Incident | None:
    return session.get(Incident, incident_id)

def find_alerts_by_incident_id(
    session: Session,
    incident_id: UUID
) -> list[Alert]:
    statement = (
        select(Alert)
        .join(IncidentAlert, IncidentAlert.alert_id == Alert.id) #type: ignore
        .where(IncidentAlert.incident_id == incident_id)
        .order_by(asc(Alert.received_at))
    )

    return list(session.exec(statement).all())

def _highest_severity(current: str, incoming: str) -> str:
    current_rank = SEVERITY_RANK.get(current, SEVERITY_RANK["unknown"])
    incoming_rank = SEVERITY_RANK.get(incoming, SEVERITY_RANK["unknown"])

    if incoming_rank > current_rank:
        return incoming

    return current
