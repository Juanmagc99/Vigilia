from uuid import uuid4

from app.core.config import settings
from app.db.models.outbox_event import OutboxEvent
from app.events.outbox_publisher import KafkaOutboxPublisher


class FakeProducer:
    def __init__(
        self,
        *,
        delivery_errors: dict[str, str] | None = None,
        remaining_after_flush: int = 0,
    ) -> None:
        self.produced: list[dict] = []
        self.flush_timeouts: list[float] = []
        self.delivery_errors = delivery_errors or {}
        self.remaining_after_flush = remaining_after_flush

    def produce(self, **kwargs) -> None:
        self.produced.append(kwargs)

    def flush(self, timeout: float) -> int:
        self.flush_timeouts.append(timeout)

        if self.remaining_after_flush == 0:
            for produced in self.produced:
                produced["on_delivery"](
                    self.delivery_errors.get(produced["key"]),
                    None,
                )

        return self.remaining_after_flush


def build_outbox_event(key: str) -> OutboxEvent:
    return OutboxEvent(
        id=uuid4(),
        topic="alerts.received",
        key=key,
        payload={"alert_id": str(uuid4()), "service": key},
    )


def test_publishes_a_claimed_batch_with_one_flush() -> None:
    producer = FakeProducer()
    publisher = KafkaOutboxPublisher(producer=producer)
    events = [build_outbox_event("payments"), build_outbox_event("catalog")]

    result = publisher.publish(events)

    assert result.published_event_ids == [event.id for event in events]
    assert result.failures == {}
    assert len(producer.produced) == 2
    assert producer.flush_timeouts == [settings.kafka_flush_timeout_seconds]
    assert {message["key"] for message in producer.produced} == {
        "payments",
        "catalog",
    }


def test_records_delivery_errors_per_event() -> None:
    producer = FakeProducer(delivery_errors={"catalog": "broker unavailable"})
    publisher = KafkaOutboxPublisher(producer=producer)
    payments = build_outbox_event("payments")
    catalog = build_outbox_event("catalog")

    result = publisher.publish([payments, catalog])

    assert result.published_event_ids == [payments.id]
    assert result.failures == {catalog.id: "broker unavailable"}


def test_records_unconfirmed_events_when_flush_times_out() -> None:
    producer = FakeProducer(remaining_after_flush=2)
    publisher = KafkaOutboxPublisher(producer=producer)
    events = [build_outbox_event("payments"), build_outbox_event("catalog")]

    result = publisher.publish(events)

    assert result.published_event_ids == []
    assert result.failures == {
        event.id: "Kafka delivery timed out before confirmation"
        for event in events
    }
