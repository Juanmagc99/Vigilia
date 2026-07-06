from datetime import timedelta

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.core.config import settings
from app.core.errors import DatabaseAppError
from app.core.logging import get_logger
from app.db.models.alert import Alert
from app.db.models.incident import Incident
from app.repositories.incident_repository import (
    attach_alert_to_incident,
    create_incident_from_alert,
    find_open_incident_by_fingerprint,
    find_recent_open_incident_for_service,
    get_latest_alert_statuses_for_incident,
    resolve_incident,
    update_incident_activity,
)


logger = get_logger(__name__)


def correlate_alert(session: Session, alert: Alert) -> Incident | None:
    try:
        if alert.status == "firing":
            incident = correlate_firing_alert(session, alert)
        elif alert.status == "resolved":
            incident = correlate_resolved_alert(session, alert)
        else:
            logger.info(
                "Alert status ignored for incident correlation alert_id=%s status=%s",
                alert.id,
                alert.status,
            )
            return None

        session.commit()

        if incident is not None:
            session.refresh(incident)

        return incident
    except SQLAlchemyError as exc:
        session.rollback()
        raise DatabaseAppError(
            message="Could not correlate alert with incident",
            metadata={
                "operation": "correlate_alert",
                "alert_id": str(alert.id),
                "fingerprint": alert.fingerprint,
                "status": alert.status,
                "service": alert.service,
            },
        ) from exc


def correlate_firing_alert(session: Session, alert: Alert) -> Incident:
    since = alert.received_at - timedelta(
        minutes=settings.incident_correlation_window_minutes
    )

    incident = find_recent_open_incident_for_service(
        session=session,
        service=alert.service,
        since=since,
    )

    if incident is None:
        incident = create_incident_from_alert(session, alert)

    attach_alert_to_incident(session, incident, alert)

    return update_incident_activity(session, incident, alert)


def correlate_resolved_alert(session: Session, alert: Alert) -> Incident | None:
    incident = find_open_incident_by_fingerprint(
        session=session,
        fingerprint=alert.fingerprint,
    )

    if incident is None:
        logger.info(
            "Resolved alert has no open incident alert_id=%s fingerprint=%s",
            alert.id,
            alert.fingerprint,
        )
        return None

    attach_alert_to_incident(session, incident, alert)

    latest_statuses = get_latest_alert_statuses_for_incident(
        session=session,
        incident_id=incident.id,
    )

    if latest_statuses and all(
        status == "resolved" for status in latest_statuses.values()
    ):
        return resolve_incident(session, incident, alert.received_at)

    return update_incident_activity(session, incident, alert)
