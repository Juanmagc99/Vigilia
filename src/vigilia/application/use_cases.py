from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from vigilia.application.contracts import (
    AlertIngestionResult,
    AlertRead,
    EventEnvelope,
    IncidentDetail,
    IncidentSummary,
    InvestigationAttemptRead,
    InvestigationRead,
    LegacyReportRead,
)
from vigilia.application.errors import (
    ConflictAppError,
    NotFoundAppError,
    PermanentInvestigationError,
    TransientInvestigationError,
)
from vigilia.application.ports import (
    IncidentAnalyzer,
    InvestigationEntity,
    KnowledgeRetriever,
    UnitOfWork,
    UnitOfWorkFactory,
)
from vigilia.domain.correlation import (
    correlation_cutoff,
    highest_severity,
    should_resolve,
)
from vigilia.domain.models import (
    AlertEvidence,
    AnalysisOutput,
    IncidentSnapshot,
    InvestigationContext,
    NormalizedAlert,
)
from vigilia.observability.logging import get_logger

logger = get_logger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC)


def investigation_read(model: InvestigationEntity, attempts=()) -> InvestigationRead:
    return InvestigationRead(
        id=model.id,
        incident_id=model.incident_id,
        incident_revision=model.incident_revision,
        analyzer_version=model.analyzer_version,
        status=model.status,
        attempt_count=model.attempt_count,
        result_schema=model.result_schema,
        result=model.result,
        error_code=model.error_code,
        error_message=model.error_message,
        requested_at=model.requested_at,
        started_at=model.started_at,
        completed_at=model.completed_at,
        next_attempt_at=model.next_attempt_at,
        attempts=[InvestigationAttemptRead.model_validate(item) for item in attempts],
    )


async def queue_event(
    uow: UnitOfWork,
    *,
    event_type: str,
    aggregate_id: UUID,
    correlation_id: UUID,
    payload: dict,
    topic: str,
    key: str,
    causation_id: UUID | None = None,
    available_at: datetime | None = None,
) -> EventEnvelope:
    envelope = EventEnvelope(
        event_type=event_type,
        aggregate_id=aggregate_id,
        occurred_at=utcnow(),
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=payload,
    )
    await uow.add_outbox_event(
        event_id=envelope.event_id,
        topic=topic,
        key=key,
        payload=envelope.model_dump(mode="json"),
        available_at=available_at or utcnow(),
    )
    return envelope


class IngestAlerts:
    def __init__(self, uow_factory: UnitOfWorkFactory, alerts_topic: str) -> None:
        self._uow_factory = uow_factory
        self._alerts_topic = alerts_topic

    async def execute(
        self, alerts: list[NormalizedAlert], alerts_received: int
    ) -> AlertIngestionResult:
        async with self._uow_factory() as uow:
            saved = await uow.save_alerts(alerts)
            for alert in saved:
                await queue_event(
                    uow,
                    event_type="alerts.received.v1",
                    aggregate_id=alert.id,
                    correlation_id=alert.id,
                    payload={"alert_id": str(alert.id)},
                    topic=self._alerts_topic,
                    key=alert.service,
                )
        return AlertIngestionResult(
            alerts_received=alerts_received,
            alerts_normalized=len(alerts),
            alerts_persisted=len(saved),
            events_queued=len(saved),
        )


class CorrelateAlert:
    consumer_name = "incident-correlator-v1"

    def __init__(self, uow_factory: UnitOfWorkFactory, window_minutes: int) -> None:
        self._uow_factory = uow_factory
        self._window_minutes = window_minutes

    async def execute(self, event_id: UUID, alert_id: UUID) -> bool:
        async with self._uow_factory() as uow:
            if await uow.is_event_processed(self.consumer_name, event_id):
                return True
            alert = await uow.find_alert(alert_id)
            if alert is None:
                await uow.mark_event_processed(self.consumer_name, event_id)
                return True
            await uow.lock_correlation_service(alert.service)
            incident = None
            if alert.status == "firing":
                incident = await uow.find_recent_open_incident(
                    alert.service,
                    correlation_cutoff(alert.received_at, self._window_minutes),
                )
                if incident is None:
                    incident = await uow.create_incident(
                        id=uuid4(),
                        revision=0,
                        status="open",
                        service=alert.service,
                        severity=alert.severity,
                        title=alert.alert_name
                        or alert.summary
                        or f"Incident in {alert.service}",
                        started_at=alert.starts_at,
                        updated_at=alert.received_at,
                        resolved_at=None,
                        created_at=utcnow(),
                    )
            elif alert.status == "resolved":
                incident = await uow.find_open_incident_by_fingerprint(
                    alert.fingerprint
                )
            if incident is not None:
                attached = await uow.attach_alert(incident.id, alert.id)
                if attached:
                    incident.revision += 1
                    incident.updated_at = alert.received_at
                    incident.severity = highest_severity(
                        incident.severity, alert.severity
                    )
                    if alert.status == "resolved" and should_resolve(
                        await uow.latest_alert_statuses(incident.id)
                    ):
                        incident.status = "resolved"
                        incident.resolved_at = alert.received_at
            await uow.mark_event_processed(self.consumer_name, event_id)
        return True


class IncidentQueries:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def list(self) -> list[IncidentSummary]:
        async with self._uow_factory() as uow:
            return [
                IncidentSummary.model_validate(item)
                for item in await uow.list_incidents()
            ]

    async def get(self, incident_id: UUID) -> IncidentDetail:
        async with self._uow_factory() as uow:
            incident = await uow.find_incident(incident_id)
            if incident is None:
                raise NotFoundAppError(
                    message="Incident not found",
                    metadata={"incident_id": str(incident_id)},
                )
            alerts = await uow.list_incident_alerts(incident_id)
            summary = IncidentSummary.model_validate(incident)
            return IncidentDetail(
                **summary.model_dump(),
                alerts=[AlertRead.model_validate(alert) for alert in alerts],
            )


class InvestigationQueries:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def get(self, investigation_id: UUID) -> InvestigationRead:
        async with self._uow_factory() as uow:
            investigation = await uow.find_investigation(investigation_id)
            if investigation is None:
                raise NotFoundAppError(message="Investigation not found")
            attempts = await uow.list_attempts(investigation.id)
            return investigation_read(investigation, attempts)

    async def list_for_incident(self, incident_id: UUID) -> list[InvestigationRead]:
        async with self._uow_factory() as uow:
            if await uow.find_incident(incident_id) is None:
                raise NotFoundAppError(message="Incident not found")
            result = []
            for investigation in await uow.list_investigations(incident_id):
                attempts = await uow.list_attempts(investigation.id)
                result.append(investigation_read(investigation, attempts))
            return result

    async def list_legacy_reports(self, incident_id: UUID) -> list[LegacyReportRead]:
        async with self._uow_factory() as uow:
            if await uow.find_incident(incident_id) is None:
                raise NotFoundAppError(message="Incident not found")
            return [
                LegacyReportRead.model_validate(report)
                for report in await uow.list_legacy_reports(incident_id)
            ]


class RequestInvestigation:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        analyzer_version: str,
        requested_topic: str,
    ) -> None:
        self._uow_factory = uow_factory
        self._analyzer_version = analyzer_version
        self._requested_topic = requested_topic

    async def execute(
        self, incident_id: UUID, idempotency_key: str | None
    ) -> InvestigationRead:
        async with self._uow_factory() as uow:
            incident = await uow.find_incident(incident_id, lock=True)
            if incident is None:
                raise NotFoundAppError(message="Incident not found")
            if idempotency_key:
                existing = await uow.find_investigation_by_idempotency_key(
                    incident_id, idempotency_key
                )
                if existing:
                    return investigation_read(existing)
            active = await uow.find_active_investigation(
                incident_id, incident.revision, self._analyzer_version
            )
            if active:
                raise ConflictAppError(
                    message="An investigation is already active for this incident revision",
                    code="investigation_already_active",
                    metadata={"investigation_id": str(active.id)},
                )
            now = utcnow()
            investigation = await uow.create_investigation(
                id=uuid4(),
                incident_id=incident.id,
                incident_revision=incident.revision,
                analyzer_version=self._analyzer_version,
                idempotency_key=idempotency_key,
                status="queued",
                attempt_count=0,
                result_schema=None,
                result=None,
                error_code=None,
                error_message=None,
                requested_at=now,
                started_at=None,
                completed_at=None,
                next_attempt_at=now,
                attempt_token=None,
                lease_expires_at=None,
            )
            await queue_event(
                uow,
                event_type="investigations.requested.v1",
                aggregate_id=investigation.id,
                correlation_id=investigation.id,
                payload={"investigation_id": str(investigation.id)},
                topic=self._requested_topic,
                key=str(investigation.id),
            )
            return investigation_read(investigation)


class ExecuteInvestigation:
    consumer_name = "investigation-worker-v1"

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        analyzer: IncidentAnalyzer,
        requested_topic: str,
        lease_seconds: int,
        max_attempts: int,
        max_retry_delay_seconds: int,
        knowledge_retriever: KnowledgeRetriever | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._analyzer = analyzer
        self._requested_topic = requested_topic
        self._lease_seconds = lease_seconds
        self._max_attempts = max_attempts
        self._max_retry_delay_seconds = max_retry_delay_seconds
        self._knowledge_retriever = knowledge_retriever

    async def execute(
        self, event_id: UUID, investigation_id: UUID, causation_id: UUID | None
    ) -> bool:
        claimed = await self._claim(event_id, investigation_id)
        if claimed is None:
            return False
        if claimed is True:
            return True
        token, snapshot = claimed
        try:
            knowledge = (
                await self._knowledge_retriever.retrieve(snapshot)
                if self._knowledge_retriever
                else ()
            )
            output = await self._analyzer.analyze(
                InvestigationContext(incident=snapshot, knowledge=knowledge)
            )
            if knowledge:
                output = replace(
                    output,
                    result=replace(
                        output.result,
                        retrieved_knowledge=tuple(
                            {
                                "evidence_id": f"knowledge:{item.id}",
                                "document_id": str(item.document_id),
                                "service": item.service,
                                "title": item.title,
                                "source": item.source,
                                "version": item.version,
                                "similarity": item.similarity,
                                "content": item.content,
                            }
                            for item in knowledge
                        ),
                    ),
                )
        except TransientInvestigationError as exc:
            await self._record_failure(
                event_id,
                investigation_id,
                token,
                exc.code,
                exc.message,
                causation_id,
                retryable=True,
            )
            return True
        except PermanentInvestigationError as exc:
            await self._record_failure(
                event_id,
                investigation_id,
                token,
                exc.code,
                exc.message,
                causation_id,
                retryable=False,
            )
            return True
        except Exception:
            logger.exception(
                "Unexpected investigation failure investigation_id=%s", investigation_id
            )
            await self._record_failure(
                event_id,
                investigation_id,
                token,
                "unexpected_investigation_error",
                "The investigation failed unexpectedly",
                causation_id,
                retryable=False,
            )
            return True
        await self._complete(event_id, investigation_id, token, output)
        return True

    async def _claim(self, event_id: UUID, investigation_id: UUID):
        async with self._uow_factory() as uow:
            if await uow.is_event_processed(self.consumer_name, event_id):
                return True
            investigation = await uow.find_investigation(investigation_id, lock=True)
            if investigation is None:
                await uow.mark_event_processed(self.consumer_name, event_id)
                return True
            now = utcnow()
            if investigation.status in ("completed", "failed"):
                await uow.mark_event_processed(self.consumer_name, event_id)
                return True
            if investigation.status == "running" and investigation.lease_expires_at:
                if investigation.lease_expires_at > now:
                    return None
                expired_attempt = await uow.find_attempt_by_token(
                    investigation.attempt_token
                )
                if expired_attempt:
                    expired_attempt.status = "failed"
                    expired_attempt.finished_at = now
                    expired_attempt.error_code = "lease_expired"
                    expired_attempt.error_message = (
                        "Worker lease expired before completion"
                    )
            if investigation.next_attempt_at and investigation.next_attempt_at > now:
                return None
            incident = await uow.find_incident(investigation.incident_id)
            if incident is None:
                investigation.status = "failed"
                investigation.error_code = "incident_not_found"
                investigation.error_message = "Incident no longer exists"
                investigation.completed_at = now
                await uow.mark_event_processed(self.consumer_name, event_id)
                return True
            alerts = await uow.list_incident_alerts(incident.id)
            token = uuid4()
            investigation.status = "running"
            investigation.attempt_count += 1
            investigation.attempt_token = token
            investigation.lease_expires_at = now + timedelta(
                seconds=self._lease_seconds
            )
            investigation.started_at = investigation.started_at or now
            investigation.next_attempt_at = None
            await uow.create_attempt(
                id=uuid4(),
                investigation_id=investigation.id,
                attempt_number=investigation.attempt_count,
                attempt_token=token,
                status="running",
                started_at=now,
                finished_at=None,
                error_code=None,
                error_message=None,
                provider=self._analyzer.provider,
                model=self._analyzer.model,
                provider_response_id=None,
                prompt_tokens=None,
                cached_prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
                estimated_cost_usd=None,
                latency_ms=None,
            )
            snapshot = IncidentSnapshot(
                id=incident.id,
                revision=investigation.incident_revision,
                status=incident.status,
                service=incident.service,
                severity=incident.severity,
                title=incident.title,
                started_at=incident.started_at,
                updated_at=incident.updated_at,
                resolved_at=incident.resolved_at,
                alerts=tuple(
                    AlertEvidence(
                        id=alert.id,
                        fingerprint=alert.fingerprint,
                        status=alert.status,
                        alert_name=alert.alert_name,
                        service=alert.service,
                        severity=alert.severity,
                        summary=alert.summary,
                        description=alert.description,
                        starts_at=alert.starts_at,
                        ends_at=alert.ends_at,
                        received_at=alert.received_at,
                    )
                    for alert in alerts
                ),
            )
            return token, snapshot

    async def _complete(
        self,
        event_id: UUID,
        investigation_id: UUID,
        token: UUID,
        output: AnalysisOutput,
    ) -> None:
        async with self._uow_factory() as uow:
            investigation = await uow.find_investigation(investigation_id, lock=True)
            if investigation is None or investigation.attempt_token != token:
                await uow.mark_event_processed(self.consumer_name, event_id)
                return
            now = utcnow()
            investigation.status = "completed"
            investigation.result_schema = output.result.schema
            investigation.result = output.result.as_json()
            investigation.completed_at = now
            investigation.error_code = None
            investigation.error_message = None
            investigation.attempt_token = None
            investigation.lease_expires_at = None
            attempt = await uow.find_attempt_by_token(token)
            if attempt:
                attempt.status = "completed"
                attempt.finished_at = now
                attempt.provider = output.usage.provider
                attempt.model = output.usage.model
                attempt.provider_response_id = output.usage.response_id
                attempt.prompt_tokens = output.usage.prompt_tokens
                attempt.cached_prompt_tokens = output.usage.cached_prompt_tokens
                attempt.completion_tokens = output.usage.completion_tokens
                attempt.total_tokens = output.usage.total_tokens
                attempt.estimated_cost_usd = output.usage.estimated_cost_usd
                attempt.latency_ms = output.usage.latency_ms
            await uow.mark_event_processed(self.consumer_name, event_id)

    async def _record_failure(
        self,
        event_id: UUID,
        investigation_id: UUID,
        token: UUID,
        error_code: str,
        error_message: str,
        causation_id: UUID | None,
        *,
        retryable: bool,
    ) -> None:
        async with self._uow_factory() as uow:
            investigation = await uow.find_investigation(investigation_id, lock=True)
            if investigation is None or investigation.attempt_token != token:
                await uow.mark_event_processed(self.consumer_name, event_id)
                return
            now = utcnow()
            attempt = await uow.find_attempt_by_token(token)
            if attempt:
                attempt.status = "failed"
                attempt.finished_at = now
                attempt.error_code = error_code
                attempt.error_message = error_message
            investigation.error_code = error_code
            investigation.error_message = error_message
            investigation.attempt_token = None
            investigation.lease_expires_at = None
            if not retryable or investigation.attempt_count >= self._max_attempts:
                investigation.status = "failed"
                investigation.completed_at = now
                investigation.next_attempt_at = None
            else:
                delay = min(
                    2**investigation.attempt_count,
                    self._max_retry_delay_seconds,
                )
                investigation.status = "retry_wait"
                investigation.next_attempt_at = now + timedelta(seconds=delay)
                await queue_event(
                    uow,
                    event_type="investigations.requested.v1",
                    aggregate_id=investigation.id,
                    correlation_id=investigation.id,
                    causation_id=causation_id or event_id,
                    payload={"investigation_id": str(investigation.id)},
                    topic=self._requested_topic,
                    key=str(investigation.id),
                    available_at=investigation.next_attempt_at,
                )
            await uow.mark_event_processed(self.consumer_name, event_id)
