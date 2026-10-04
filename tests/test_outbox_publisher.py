from types import SimpleNamespace
from uuid import uuid4

from vigilia.adapters.messaging.kafka import publish_batch


class FakeProducer:
    def __init__(self, delivery_errors: dict[str, str] | None = None) -> None:
        self.produced: list[dict] = []
        self.delivery_errors = delivery_errors or {}

    def produce(self, **kwargs) -> None:
        self.produced.append(kwargs)

    def flush(self, timeout: float) -> int:
        for message in self.produced:
            message["on_delivery"](self.delivery_errors.get(message["key"]), None)
        return 0


def build_event(key: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(), topic="alerts.received.v1", key=key, payload={"service": key}
    )


def test_publishes_outbox_batch_and_tracks_delivery_failures() -> None:
    producer = FakeProducer(delivery_errors={"catalog": "broker unavailable"})
    payments, catalog = build_event("payments"), build_event("catalog")

    result = publish_batch(
        producer,
        [payments, catalog],
        1.0,
    )

    assert result.published == [payments.id]
    assert result.failed == {catalog.id: "broker unavailable"}
    assert len(producer.produced) == 2
