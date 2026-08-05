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
    def publish_alerts_received(self, alerts: list[Alert]) -> None:
        ...
    
class NoopAlertEventPublisher:
    def publish_alerts_received(self, alerts: list[Alert]) -> None:
        return None


class KafkaAlertEventPublisher:
    def __init__(self, producer: Producer, topic: str) -> None:
        self.producer = producer
        self.topic = topic

    def publish_alerts_received(self, alerts: list[Alert]) -> None:
        delivery_errors: list[str] = []

        def on_delivery(error, _message) -> None:
            if error is not None:
                delivery_errors.append(str(error))

        try:
            for alert in alerts:
                message = build_alert_received_message(alert)
                self.producer.produce(
                    topic=self.topic,
                    key=alert.service,
                    value=message.model_dump_json(),
                    on_delivery=on_delivery,
                )

            remaining = self.producer.flush(
                timeout=settings.kafka_flush_timeout_seconds,
            )

            if remaining or delivery_errors:
                raise ExternalServiceAppError(
                    message="Could not deliver all alert events",
                    metadata={
                        "operation": "publish_alerts_received",
                        "topic": self.topic,
                        "alert_count": len(alerts),
                        "remaining": remaining,
                        "delivery_errors": delivery_errors,
                    },
                )

            logger.info(
                "Published alert events topic=%s event_type=alert.received count=%s",
                self.topic,
                len(alerts),
            )
        except ExternalServiceAppError:
            raise
        except Exception as exc:
            raise ExternalServiceAppError(
                message="Could not publish alert events",
                metadata={
                    "operation": "publish_alerts_received",
                    "topic": self.topic,
                    "alert_count": len(alerts),
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
            "acks": "all",
            "enable.idempotence": True,
            "delivery.timeout.ms": int(
                settings.kafka_flush_timeout_seconds * 1000
            ),
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
