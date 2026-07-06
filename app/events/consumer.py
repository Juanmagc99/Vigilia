from confluent_kafka import Consumer
from pydantic import ValidationError
from sqlmodel import Session

from app.core.errors import AppError
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import engine
from app.events.message import AlertReceivedMessage
from app.repositories.alert_repository import get_alert_by_id
from app.services.incident_correlation_service import correlate_alert


logger = get_logger(__name__)


def create_alert_received_consumer() -> Consumer:
    return Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": "vigilia-alert-correlator",
            "auto.offset.reset": "earliest",
        }
    )


def handle_alert_received(message: AlertReceivedMessage) -> None:
    with Session(engine) as session:
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


def run_alert_received_consumer() -> None:
    consumer = create_alert_received_consumer()
    consumer.subscribe([settings.alerts_received_topic])

    logger.info("Alert event consumer started topic=%s", settings.alerts_received_topic)

    try:
        while True:
            kafka_message = consumer.poll(timeout=1.0)

            if kafka_message is None:
                continue

            if kafka_message.error():
                logger.warning("Kafka consumer error error=%s", kafka_message.error())
                continue

            try:
                raw_value = kafka_message.value().decode("utf-8")
                message = AlertReceivedMessage.model_validate_json(raw_value)
                handle_alert_received(message)
            except ValidationError as exc:
                logger.warning("Invalid alert event message error=%s", exc)
            except AppError:
                logger.exception("Application error while handling alert event")
            except Exception:
                logger.exception("Unexpected error while handling alert event")

    except KeyboardInterrupt:
        logger.info("Alert event consumer stopped")
    finally:
        consumer.close()


if __name__ == "__main__":
    configure_logging()
    run_alert_received_consumer()
