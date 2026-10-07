import asyncio
import json
from dataclasses import dataclass, field
from functools import partial
from uuid import UUID

from confluent_kafka import Consumer, KafkaError, Message, Producer, TopicPartition

from vigilia.adapters.messaging.contracts import IncomingEvent
from vigilia.application.contracts import EventEnvelope


def create_consumer(bootstrap_servers: str) -> Consumer:
    return Consumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": "vigilia-worker-v1",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )


def create_producer(bootstrap_servers: str) -> Producer:
    return Producer(
        {
            "bootstrap.servers": bootstrap_servers,
            "client.id": "vigilia-outbox-publisher-v1",
            "acks": "all",
            "enable.idempotence": True,
        }
    )


def decode_message(message: Message) -> IncomingEvent:
    raw = json.loads(message.value().decode("utf-8"))
    envelope = EventEnvelope.model_validate(raw)
    return IncomingEvent(
        envelope=envelope,
        topic=message.topic(),
        partition=message.partition(),
        offset=message.offset(),
    )


async def poll(consumer: Consumer, timeout: float) -> Message | None:
    return await asyncio.to_thread(consumer.poll, timeout)


async def commit(consumer: Consumer, message: Message) -> None:
    await asyncio.to_thread(consumer.commit, message=message, asynchronous=False)


async def retry_from_same_offset(consumer: Consumer, event: IncomingEvent) -> None:
    await asyncio.to_thread(
        consumer.seek, TopicPartition(event.topic, event.partition, event.offset)
    )


@dataclass
class DeliveryTracker:
    published: list[UUID] = field(default_factory=list)
    failed: dict[UUID, str] = field(default_factory=dict)

    def callback(self, event_id: UUID, error: KafkaError | None, _: Message) -> None:
        if error is None:
            self.published.append(event_id)
        else:
            self.failed[event_id] = str(error)


def publish_batch(
    producer: Producer, events: list, flush_timeout_seconds: float
) -> DeliveryTracker:
    tracker = DeliveryTracker()
    for event in events:
        try:
            producer.produce(
                topic=event.topic,
                key=event.key,
                value=json.dumps(event.payload, separators=(",", ":")),
                on_delivery=partial(tracker.callback, event.id),
            )
        except Exception as exc:
            tracker.failed[event.id] = str(exc)
    remaining = producer.flush(flush_timeout_seconds)
    if remaining:
        for event in events:
            if event.id not in tracker.published:
                tracker.failed.setdefault(event.id, "Kafka delivery timed out")
    return tracker
