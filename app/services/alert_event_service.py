from sqlmodel import Session

from app.core.logging import get_logger
from app.events.message import AlertReceivedMessage
from app.repositories.alert_repository import get_alert_by_id
from app.services.incident_correlation_service import correlate_alert


logger = get_logger(__name__)


def handle_alert_received_event(
    session: Session,
    message: AlertReceivedMessage,
) -> None:
    alert = get_alert_by_id(session, message.alert_id)

    if alert is None:
        logger.warning(
            "Alert not found for event alert_id=%s event_type=%s",
            message.alert_id,
            message.event_type,
        )
        return

    incident = correlate_alert(session=session, alert=alert)

    if incident is None:
        logger.info(
            "Consumed alert event without incident alert_id=%s status=%s fingerprint=%s",
            alert.id,
            alert.status,
            alert.fingerprint,
        )
        return

    logger.info(
        "Correlated alert event alert_id=%s incident_id=%s incident_status=%s service=%s",
        alert.id,
        incident.id,
        incident.status,
        incident.service,
    )
