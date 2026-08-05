from datetime import datetime, timezone
from uuid import uuid4

from app.core.config import settings
from app.db.models.alert import Alert
from app.events.publisher import KafkaAlertEventPublisher


class FakeProducer:
    def __init__(self) -> None:
        self.produced: list[dict] = []
        self.flush_timeouts: list[float] = []

    def produce(self, **kwargs) -> None:
        self.produced.append(kwargs)

    def flush(self, timeout: float) -> int:
        self.flush_timeouts.append(timeout)

        for produced in self.produced:
            produced["on_delivery"](None, None)

        return 0


def build_alert(service: str) -> Alert:
    now = datetime.now(timezone.utc)
    return Alert(
        id=uuid4(),
        source="grafana",
        fingerprint=f"fingerprint-{service}",
        status="firing",
        service=service,
        severity="warning",
        labels={},
        annotations={},
        starts_at=now,
        received_at=now,
    )


def test_publishes_all_alerts_before_flushing_once() -> None:
    producer = FakeProducer()
    publisher = KafkaAlertEventPublisher(
        producer=producer,
        topic="alerts.received",
    )

    publisher.publish_alerts_received(
        [build_alert("payments"), build_alert("catalog")]
    )

    assert len(producer.produced) == 2
    assert producer.flush_timeouts == [settings.kafka_flush_timeout_seconds]
    assert {message["key"] for message in producer.produced} == {
        "payments",
        "catalog",
    }
