import asyncio
from uuid import UUID

from pydantic import ValidationError

from vigilia.adapters.messaging.kafka import (
    commit,
    create_consumer,
    decode_message,
    poll,
    retry_from_same_offset,
)
from vigilia.bootstrap.resources import worker_resources
from vigilia.bootstrap.settings import Settings
from vigilia.observability.logging import configure_logging, get_logger


logger = get_logger(__name__)


async def run_worker() -> None:
    settings = Settings()
    async with worker_resources(settings) as application:
        consumer = create_consumer(settings.kafka_bootstrap_servers)
        consumer.subscribe(
            list(
                dict.fromkeys(
                    (
                        settings.alerts_received_topic,
                        settings.legacy_alerts_received_topic,
                        settings.investigations_requested_topic,
                    )
                )
            )
        )
        logger.info("Worker started")
        try:
            while True:
                message = await poll(consumer, settings.worker_poll_timeout_seconds)
                if message is None:
                    continue
                if message.error():
                    logger.warning("Kafka consumer error error=%s", message.error())
                    continue
                incoming = None
                try:
                    incoming = decode_message(message)
                    event = incoming.envelope
                    handled = True
                    if event.event_type == "alerts.received.v1":
                        handled = await application.correlate_alert.execute(
                            event.event_id, UUID(event.payload["alert_id"])
                        )
                    elif event.event_type == "investigations.requested.v1":
                        handled = await application.execute_investigation.execute(
                            event.event_id,
                            UUID(event.payload["investigation_id"]),
                            event.causation_id,
                        )
                    if handled:
                        await commit(consumer, message)
                    else:
                        await retry_from_same_offset(consumer, incoming)
                        await asyncio.sleep(1)
                except (ValidationError, ValueError, KeyError) as exc:
                    logger.warning("Invalid event message error=%s", exc)
                    await commit(consumer, message)
                except Exception:
                    logger.exception("Unexpected error while handling event")
                    if incoming is not None:
                        await retry_from_same_offset(consumer, incoming)
                    await asyncio.sleep(1)
        finally:
            await asyncio.to_thread(consumer.close)


def run() -> None:
    configure_logging()
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker stopped")


if __name__ == "__main__":
    run()
