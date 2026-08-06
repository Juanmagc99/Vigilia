from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.db.models.alert import Alert
from app.db.models.outbox_event import OutboxEvent
from app.events.message import AlertReceivedMessage


def save_alert_received_events(
    session: Session,
    alerts: list[Alert],
    topic: str,
) -> list[OutboxEvent]:
    events = [
        OutboxEvent(
            topic=topic,
            key=alert.service,
            payload=AlertReceivedMessage(
                alert_id=alert.id,
                source=alert.source,
                fingerprint=alert.fingerprint,
                status=alert.status,
                alert_name=alert.alert_name,
                service=alert.service,
                severity=alert.severity,
                starts_at=alert.starts_at,
                received_at=alert.received_at,
            ).model_dump(mode="json"),
        )
        for alert in alerts
    ]
    session.add_all(events)
    return events


def claim_pending_events(
    session: Session,
    *,
    claim_token: UUID,
    batch_size: int,
    lock_seconds: int,
) -> list[OutboxEvent]:
    now = datetime.now(timezone.utc)
    statement = (
        select(OutboxEvent)
        .where(col(OutboxEvent.published_at).is_(None))
        .where(col(OutboxEvent.available_at) <= now)
        .where(
            or_(
                col(OutboxEvent.locked_until).is_(None),
                col(OutboxEvent.locked_until) < now,
            )
        )
        .order_by(col(OutboxEvent.created_at))
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    events = list(session.exec(statement).all())

    lock_until = now + timedelta(seconds=lock_seconds)
    for event in events:
        event.claim_token = claim_token
        event.locked_until = lock_until
        event.attempts += 1

    session.commit()
    return events


def mark_events_published(
    session: Session,
    *,
    event_ids: list[UUID],
    claim_token: UUID,
) -> None:
    if not event_ids:
        return

    statement = (
        select(OutboxEvent)
        .where(col(OutboxEvent.id).in_(event_ids))
        .where(col(OutboxEvent.claim_token) == claim_token)
    )
    published_at = datetime.now(timezone.utc)
    for event in session.exec(statement).all():
        event.published_at = published_at
        event.claim_token = None
        event.locked_until = None
        event.last_error = None

    session.commit()


def release_events_for_retry(
    session: Session,
    *,
    failures: dict[UUID, str],
    claim_token: UUID,
    max_retry_delay_seconds: int,
) -> None:
    if not failures:
        return

    statement = (
        select(OutboxEvent)
        .where(col(OutboxEvent.id).in_(list(failures)))
        .where(col(OutboxEvent.claim_token) == claim_token)
    )
    now = datetime.now(timezone.utc)
    for event in session.exec(statement).all():
        retry_delay = min(2 ** min(event.attempts, 8), max_retry_delay_seconds)
        event.available_at = now + timedelta(seconds=retry_delay)
        event.claim_token = None
        event.locked_until = None
        event.last_error = failures[event.id]

    session.commit()
