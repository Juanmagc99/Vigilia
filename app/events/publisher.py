from typing import Annotated, Protocol

from confluent_kafka import Producer
from fastapi import Depends

from app.core.config import settings
from app.core.errors import ExternalServiceAppError
from app.core.logging import get_logger
from app.db.models.alert import Alert
from app.events.message import AlertReceivedMessage


logger = get_logger(__name__)


class AlertEventPublisher(Protocol):
    def publish_alert_received(self, alert: Alert) -> None:
        ...
    
class NoopAlertEventPublisher:
    def publish_alert_received(self, alert: Alert) -> None:
        return None


class KafkaAlertEventPublisher:
    def __init__(self, producer: Producer, topic: str) -> None:
        self.producer = producer
        self.topic = topic

    def publish_alert_received(self, alert: Alert) -> None:
        message = build_alert_received_message(alert)

        try:
            self.producer.produce(
                topic=self.topic,
                key=alert.service,
                value=message.model_dump_json(),
            )
            self.producer.flush()
            logger.info(
                "Published alert event topic=%s event_type=%s alert_id=%s service=%s",
                self.topic,
                message.event_type,
                message.alert_id,
                message.service,
            )
        except Exception as exc:
            raise ExternalServiceAppError(
                message="Could not publish alert event",
                metadata={
                    "operation": "publish_alert_received",
                    "topic": self.topic,
                    "event_type": message.event_type,
                    "alert_id": str(message.alert_id),
                    "service": message.service,
                },
            ) from exc

def build_alert_received_message(alert: Alert) -> AlertReceivedMessage:
    return AlertReceivedMessage(
        alert_id=alert.id,
        source=alert.source,
        fingerprint=alert.fingerprint,
        status=alert.status,
        alert_name=alert.alert_name,
        service=alert.service,
        severity=alert.severity,
        starts_at=alert.starts_at,
        received_at=alert.received_at,
    )

def get_alert_event_publisher() -> AlertEventPublisher:
    producer = Producer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
        }
    )
    return KafkaAlertEventPublisher(
        producer=producer,
        topic=settings.alerts_received_topic,
    )

AlertEventPublisherDependency = Annotated[
    AlertEventPublisher,
    Depends(get_alert_event_publisher),
]
