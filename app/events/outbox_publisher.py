import json
import time
from dataclasses import dataclass, field
from functools import partial
from uuid import UUID, uuid4

from confluent_kafka import KafkaError, Message, Producer
from sqlmodel import Session

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.models.outbox_event import OutboxEvent
from app.db.session import engine
from app.repositories.outbox_repository import (
    claim_pending_events,
    mark_events_published,
    release_events_for_retry,
)


logger = get_logger(__name__)


@dataclass(frozen=True)
class OutboxPublishResult:
    published_event_ids: list[UUID]
    failures: dict[UUID, str]


@dataclass
class DeliveryTracker:
    published_event_ids: list[UUID] = field(default_factory=list)
    failures: dict[UUID, str] = field(default_factory=dict)

    def record_delivery(
        self,
        event_id: UUID,
        error: KafkaError | None,
        _message: Message,
    ) -> None:
        if error is None:
            self.published_event_ids.append(event_id)
        else:
            self.failures[event_id] = str(error)

    def record_failure(self, event_id: UUID, error: Exception | str) -> None:
        self.failures[event_id] = str(error)

    def record_timeouts(self, events: list[OutboxEvent]) -> None:
        published_ids = set(self.published_event_ids)
        for event in events:
            if event.id not in published_ids:
                self.failures.setdefault(
                    event.id,
                    "Kafka delivery timed out before confirmation",
                )

    def result(self) -> OutboxPublishResult:
        return OutboxPublishResult(
            published_event_ids=list(self.published_event_ids),
            failures=dict(self.failures),
        )


class KafkaOutboxPublisher:
    def __init__(self, producer: Producer) -> None:
        self._producer = producer

    def publish(self, events: list[OutboxEvent]) -> OutboxPublishResult:
        tracker = DeliveryTracker()

        for event in events:
            try:
                self._producer.produce(
                    topic=event.topic,
                    key=event.key,
                    value=json.dumps(event.payload, separators=(",", ":")),
                    on_delivery=partial(
                        tracker.record_delivery,
                        event.id,
                    ),
                )
            except Exception as exc:
                tracker.record_failure(event.id, exc)

        remaining = self._producer.flush(
            timeout=settings.kafka_flush_timeout_seconds,
        )
        if remaining:
            tracker.record_timeouts(events)

        return tracker.result()


def create_kafka_producer() -> Producer:
    return Producer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "client.id": "vigilia-outbox-publisher",
            "acks": "all",
            "enable.idempotence": True,
            "delivery.timeout.ms": int(
                settings.kafka_flush_timeout_seconds * 1000
            ),
        }
    )


def publish_pending_events_once(publisher: KafkaOutboxPublisher) -> int:
    claim_token = uuid4()
    with Session(engine, expire_on_commit=False) as session:
        events = claim_pending_events(
            session,
            claim_token=claim_token,
            batch_size=settings.outbox_batch_size,
            lock_seconds=settings.outbox_lock_seconds,
        )

    if not events:
        return 0

    result = publisher.publish(events)

    with Session(engine) as session:
        mark_events_published(
            session,
            event_ids=result.published_event_ids,
            claim_token=claim_token,
        )
        release_events_for_retry(
            session,
            failures=result.failures,
            claim_token=claim_token,
            max_retry_delay_seconds=settings.outbox_max_retry_delay_seconds,
        )

    logger.info(
        "Published outbox batch published=%s failed=%s",
        len(result.published_event_ids),
        len(result.failures),
    )
    return len(result.published_event_ids)


def run_outbox_publisher() -> None:
    producer = create_kafka_producer()
    publisher = KafkaOutboxPublisher(producer)
    logger.info("Outbox publisher started")

    try:
        while True:
            published_count = publish_pending_events_once(publisher)
            if published_count == 0:
                time.sleep(settings.outbox_poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info("Outbox publisher stopped")
    finally:
        remaining = producer.flush(timeout=settings.kafka_flush_timeout_seconds)
        if remaining:
            logger.error(
                "Outbox publisher stopped with undelivered messages count=%s",
                remaining,
            )


if __name__ == "__main__":
    configure_logging()
    run_outbox_publisher()
