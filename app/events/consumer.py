from confluent_kafka import Consumer
from pydantic import ValidationError
from sqlmodel import Session

from app.core.errors import AppError
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import engine
from app.events.message import AlertReceivedMessage
from app.services.alert_event_service import handle_alert_received_event


logger = get_logger(__name__)


def create_alert_received_consumer() -> Consumer:
    return Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": "vigilia-alert-correlator",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )


def handle_alert_received(message: AlertReceivedMessage) -> None:
    with Session(engine) as session:
        handle_alert_received_event(
            session=session,
            message=message,
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
                raw_value = kafka_message.value().decode("utf-8") # type: ignore
                message = AlertReceivedMessage.model_validate_json(raw_value)
                handle_alert_received(message)
                consumer.commit(message=kafka_message)
            except ValidationError as exc:
                logger.warning("Invalid alert event message error=%s", exc)
                consumer.commit(message=kafka_message)
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
