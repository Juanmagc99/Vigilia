from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import asc, desc, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from vigilia.adapters.postgres.models import (
    AlertModel,
    IncidentAlertModel,
    IncidentModel,
    InvestigationAttemptModel,
    InvestigationModel,
    OutboxEventModel,
    ProcessedEventModel,
    ReportModel,
)
from vigilia.domain.models import NormalizedAlert


def utcnow() -> datetime:
    return datetime.now(UTC)


async def save_alerts(
    session: AsyncSession, alerts: list[NormalizedAlert]
) -> list[AlertModel]:
    if not alerts:
        return []
    rows = [
        {
            "source": alert.source,
            "fingerprint": alert.fingerprint,
            "status": alert.status.value,
            "alert_name": alert.alert_name,
            "service": alert.service,
            "severity": alert.severity,
            "summary": alert.summary,
            "description": alert.description,
            "labels": alert.labels,
            "annotations": alert.annotations,
            "starts_at": alert.starts_at,
            "ends_at": alert.ends_at,
            "received_at": alert.received_at,
            "dashboard_url": alert.dashboard_url,
            "panel_url": alert.panel_url,
            "silence_url": alert.silence_url,
        }
        for alert in alerts
    ]
    statement = (
        insert(AlertModel)
        .values(rows)
        .on_conflict_do_nothing(
            constraint="uq_alert_source_fingerprint_starts_at_status"
        )
        .returning(AlertModel)
    )
    return list((await session.scalars(statement)).all())


async def find_alert(session: AsyncSession, alert_id: UUID) -> AlertModel | None:
    return await session.get(AlertModel, alert_id)


async def lock_correlation_service(session: AsyncSession, service: str) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:service))"), {"service": service}
    )


async def find_recent_open_incident(
    session: AsyncSession, service: str, since: datetime
) -> IncidentModel | None:
    statement = (
        select(IncidentModel)
        .where(IncidentModel.status == "open")
        .where(IncidentModel.service == service)
        .where(IncidentModel.updated_at >= since)
        .order_by(desc(IncidentModel.updated_at))
        .with_for_update()
    )
    return (await session.scalars(statement)).first()


async def find_open_incident_by_fingerprint(
    session: AsyncSession, fingerprint: str
) -> IncidentModel | None:
    statement = (
        select(IncidentModel)
        .join(IncidentAlertModel, IncidentAlertModel.incident_id == IncidentModel.id)
        .join(AlertModel, AlertModel.id == IncidentAlertModel.alert_id)
        .where(IncidentModel.status == "open")
        .where(AlertModel.fingerprint == fingerprint)
        .order_by(desc(IncidentModel.updated_at))
        .with_for_update()
    )
    return (await session.scalars(statement)).first()


async def attach_alert(
    session: AsyncSession, incident_id: UUID, alert_id: UUID
) -> bool:
    statement = (
        insert(IncidentAlertModel)
        .values(
            incident_id=incident_id,
            alert_id=alert_id,
            created_at=utcnow(),
        )
        .on_conflict_do_nothing()
        .returning(IncidentAlertModel.alert_id)
    )
    return (await session.scalar(statement)) is not None


async def latest_alert_statuses(
    session: AsyncSession, incident_id: UUID
) -> dict[str, str]:
    statement = (
        select(AlertModel)
        .join(IncidentAlertModel, IncidentAlertModel.alert_id == AlertModel.id)
        .where(IncidentAlertModel.incident_id == incident_id)
        .order_by(asc(AlertModel.received_at))
    )
    statuses: dict[str, str] = {}
    for alert in (await session.scalars(statement)).all():
        statuses[alert.fingerprint] = alert.status
    return statuses


async def find_incident(
    session: AsyncSession, incident_id: UUID, *, lock: bool = False
) -> IncidentModel | None:
    statement = select(IncidentModel).where(IncidentModel.id == incident_id)
    if lock:
        statement = statement.with_for_update()
    return (await session.scalars(statement)).one_or_none()


async def list_incidents(session: AsyncSession) -> list[IncidentModel]:
    statement = select(IncidentModel).order_by(desc(IncidentModel.updated_at))
    return list((await session.scalars(statement)).all())


async def list_incident_alerts(
    session: AsyncSession, incident_id: UUID
) -> list[AlertModel]:
    statement = (
        select(AlertModel)
        .join(IncidentAlertModel, IncidentAlertModel.alert_id == AlertModel.id)
        .where(IncidentAlertModel.incident_id == incident_id)
        .order_by(asc(AlertModel.received_at))
    )
    return list((await session.scalars(statement)).all())


async def find_processed_event(
    session: AsyncSession, consumer_name: str, event_id: UUID
) -> ProcessedEventModel | None:
    return await session.get(ProcessedEventModel, (consumer_name, event_id))


def mark_event_processed(
    session: AsyncSession, consumer_name: str, event_id: UUID
) -> None:
    session.add(
        ProcessedEventModel(
            consumer_name=consumer_name,
            event_id=event_id,
            processed_at=utcnow(),
        )
    )


async def find_investigation(
    session: AsyncSession, investigation_id: UUID, *, lock: bool = False
) -> InvestigationModel | None:
    statement = select(InvestigationModel).where(
        InvestigationModel.id == investigation_id
    )
    if lock:
        statement = statement.with_for_update()
    return (await session.scalars(statement)).one_or_none()


async def find_investigation_by_idempotency_key(
    session: AsyncSession, incident_id: UUID, idempotency_key: str
) -> InvestigationModel | None:
    statement = select(InvestigationModel).where(
        InvestigationModel.incident_id == incident_id,
        InvestigationModel.idempotency_key == idempotency_key,
    )
    return (await session.scalars(statement)).one_or_none()


async def find_active_investigation(
    session: AsyncSession,
    incident_id: UUID,
    incident_revision: int,
    analyzer_version: str,
) -> InvestigationModel | None:
    statement = select(InvestigationModel).where(
        InvestigationModel.incident_id == incident_id,
        InvestigationModel.incident_revision == incident_revision,
        InvestigationModel.analyzer_version == analyzer_version,
        InvestigationModel.status.in_(("queued", "running", "retry_wait")),
    )
    return (await session.scalars(statement)).one_or_none()


async def list_investigations(
    session: AsyncSession, incident_id: UUID
) -> list[InvestigationModel]:
    statement = (
        select(InvestigationModel)
        .where(InvestigationModel.incident_id == incident_id)
        .order_by(desc(InvestigationModel.requested_at))
    )
    return list((await session.scalars(statement)).all())


async def list_attempts(
    session: AsyncSession, investigation_id: UUID
) -> list[InvestigationAttemptModel]:
    statement = (
        select(InvestigationAttemptModel)
        .where(InvestigationAttemptModel.investigation_id == investigation_id)
        .order_by(asc(InvestigationAttemptModel.attempt_number))
    )
    return list((await session.scalars(statement)).all())


async def list_legacy_reports(
    session: AsyncSession, incident_id: UUID
) -> list[ReportModel]:
    statement = (
        select(ReportModel)
        .where(ReportModel.incident_id == incident_id)
        .order_by(desc(ReportModel.created_at))
    )
    return list((await session.scalars(statement)).all())


async def claim_outbox_events(
    session: AsyncSession, claim_token: UUID, batch_size: int, lock_seconds: int
) -> list[OutboxEventModel]:
    now = utcnow()
    statement = (
        select(OutboxEventModel)
        .where(OutboxEventModel.published_at.is_(None))
        .where(OutboxEventModel.available_at <= now)
        .where(
            or_(
                OutboxEventModel.locked_until.is_(None),
                OutboxEventModel.locked_until < now,
            )
        )
        .order_by(OutboxEventModel.created_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    events = list((await session.scalars(statement)).all())
    from datetime import timedelta

    for event in events:
        event.claim_token = claim_token
        event.locked_until = now + timedelta(seconds=lock_seconds)
        event.attempts += 1
    return events
