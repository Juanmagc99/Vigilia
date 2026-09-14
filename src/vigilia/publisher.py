import asyncio
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select

from vigilia.adapters.messaging.kafka import create_producer, publish_batch
from vigilia.adapters.postgres.models import OutboxEventModel
from vigilia.adapters.postgres.repositories import claim_outbox_events, utcnow
from vigilia.bootstrap.resources import publisher_resources
from vigilia.bootstrap.settings import Settings
from vigilia.observability.logging import configure_logging, get_logger


logger = get_logger(__name__)


async def publish_once(application, producer) -> int:
    claim_token = uuid4()
    async with application.sessions() as session, session.begin():
        events = await claim_outbox_events(
            session,
            claim_token,
            application.settings.outbox_batch_size,
            application.settings.outbox_lock_seconds,
        )
    if not events:
        return 0

    tracker = await asyncio.to_thread(
        publish_batch,
        producer,
        events,
        application.settings.kafka_flush_timeout_seconds,
    )
    async with application.sessions() as session, session.begin():
        statement = select(OutboxEventModel).where(
            OutboxEventModel.id.in_([event.id for event in events]),
            OutboxEventModel.claim_token == claim_token,
        )
        claimed = list((await session.scalars(statement)).all())
        now = utcnow()
        for event in claimed:
            if event.id in tracker.published:
                event.published_at = now
                event.last_error = None
            else:
                delay = min(
                    2 ** min(event.attempts, 8),
                    application.settings.outbox_max_retry_delay_seconds,
                )
                event.available_at = now + timedelta(seconds=delay)
                event.last_error = tracker.failed.get(
                    event.id, "Unknown delivery failure"
                )
            event.claim_token = None
            event.locked_until = None
    logger.info(
        "Published outbox batch published=%s failed=%s",
        len(tracker.published),
        len(tracker.failed),
    )
    return len(events)


async def run_publisher() -> None:
    settings = Settings()
    producer = create_producer(settings.kafka_bootstrap_servers)
    async with publisher_resources(settings) as application:
        logger.info("Outbox publisher started")
        try:
            while True:
                handled = await publish_once(application, producer)
                if handled == 0:
                    await asyncio.sleep(settings.outbox_poll_interval_seconds)
        finally:
            await asyncio.to_thread(
                producer.flush, settings.kafka_flush_timeout_seconds
            )


def run() -> None:
    configure_logging()
    try:
        asyncio.run(run_publisher())
    except KeyboardInterrupt:
        logger.info("Outbox publisher stopped")


if __name__ == "__main__":
    run()
