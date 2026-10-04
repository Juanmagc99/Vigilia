from types import TracebackType
from typing import Any, Self

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vigilia.adapters.postgres import repositories
from vigilia.adapters.postgres.models import (
    IncidentModel,
    InvestigationAttemptModel,
    InvestigationModel,
    OutboxEventModel,
)


class SqlAlchemyUnitOfWork:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def __aenter__(self) -> Self:
        self.session = self._sessions()
        self.transaction = await self.session.begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if exc_type is None:
                await self.transaction.commit()
            else:
                await self.transaction.rollback()
        finally:
            await self.session.close()

    async def save_alerts(self, alerts):
        return await repositories.save_alerts(self.session, alerts)

    async def find_alert(self, alert_id):
        return await repositories.find_alert(self.session, alert_id)

    async def lock_correlation_service(self, service):
        await repositories.lock_correlation_service(self.session, service)

    async def find_recent_open_incident(self, service, since):
        return await repositories.find_recent_open_incident(
            self.session, service, since
        )

    async def find_open_incident_by_fingerprint(self, fingerprint):
        return await repositories.find_open_incident_by_fingerprint(
            self.session, fingerprint
        )

    async def create_incident(self, **values: Any):
        incident = IncidentModel(**values)
        self.session.add(incident)
        await self.session.flush()
        return incident

    async def attach_alert(self, incident_id, alert_id):
        return await repositories.attach_alert(self.session, incident_id, alert_id)

    async def latest_alert_statuses(self, incident_id):
        return await repositories.latest_alert_statuses(self.session, incident_id)

    async def find_incident(self, incident_id, *, lock=False):
        return await repositories.find_incident(self.session, incident_id, lock=lock)

    async def list_incidents(self):
        return await repositories.list_incidents(self.session)

    async def list_incident_alerts(self, incident_id):
        return await repositories.list_incident_alerts(self.session, incident_id)

    async def is_event_processed(self, consumer_name, event_id):
        return (
            await repositories.find_processed_event(
                self.session, consumer_name, event_id
            )
            is not None
        )

    async def mark_event_processed(self, consumer_name, event_id):
        repositories.mark_event_processed(self.session, consumer_name, event_id)

    async def add_outbox_event(
        self, *, event_id, topic, key, payload, available_at
    ) -> None:
        self.session.add(
            OutboxEventModel(
                id=event_id,
                topic=topic,
                key=key,
                payload=payload,
                created_at=repositories.utcnow(),
                available_at=available_at,
                published_at=None,
                locked_until=None,
                claim_token=None,
                attempts=0,
                last_error=None,
            )
        )

    async def create_investigation(self, **values: Any):
        investigation = InvestigationModel(**values)
        self.session.add(investigation)
        await self.session.flush()
        return investigation

    async def find_investigation(self, investigation_id, *, lock=False):
        return await repositories.find_investigation(
            self.session, investigation_id, lock=lock
        )

    async def find_investigation_by_idempotency_key(self, incident_id, idempotency_key):
        return await repositories.find_investigation_by_idempotency_key(
            self.session, incident_id, idempotency_key
        )

    async def find_active_investigation(
        self, incident_id, incident_revision, analyzer_version
    ):
        return await repositories.find_active_investigation(
            self.session, incident_id, incident_revision, analyzer_version
        )

    async def list_investigations(self, incident_id):
        return await repositories.list_investigations(self.session, incident_id)

    async def create_attempt(self, **values: Any):
        attempt = InvestigationAttemptModel(**values)
        self.session.add(attempt)
        return attempt

    async def find_attempt_by_token(self, token):
        return await self.session.scalar(
            select(InvestigationAttemptModel).where(
                InvestigationAttemptModel.attempt_token == token
            )
        )

    async def list_attempts(self, investigation_id):
        return await repositories.list_attempts(self.session, investigation_id)

    async def list_legacy_reports(self, incident_id):
        return await repositories.list_legacy_reports(self.session, incident_id)

    async def upsert_knowledge_document(self, **values: Any):
        return await repositories.upsert_knowledge_document(self.session, **values)

    async def delete_knowledge_document(self, document_id):
        return await repositories.delete_knowledge_document(self.session, document_id)

    async def search_knowledge_chunks(self, **values: Any):
        return await repositories.search_knowledge_chunks(self.session, **values)


def create_unit_of_work_factory(sessions: async_sessionmaker[AsyncSession]):
    return lambda: SqlAlchemyUnitOfWork(sessions)
