from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Any, Protocol, Self
from uuid import UUID

from vigilia.domain.models import (
    AnalysisOutput,
    IncidentSnapshot,
    InvestigationContext,
    KnowledgeChunkRecord,
    KnowledgeEvidence,
    NormalizedAlert,
)


class AlertEntity(Protocol):
    id: UUID
    source: str
    fingerprint: str
    status: str
    alert_name: str | None
    service: str
    severity: str
    summary: str | None
    description: str | None
    labels: dict[str, str]
    annotations: dict[str, str]
    starts_at: datetime
    ends_at: datetime | None
    received_at: datetime
    dashboard_url: str | None
    panel_url: str | None
    silence_url: str | None


class IncidentEntity(Protocol):
    id: UUID
    revision: int
    status: str
    service: str
    severity: str
    title: str
    started_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    created_at: datetime


class InvestigationEntity(Protocol):
    id: UUID
    incident_id: UUID
    incident_revision: int
    analyzer_version: str
    idempotency_key: str | None
    status: str
    attempt_count: int
    result_schema: str | None
    result: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    next_attempt_at: datetime | None
    attempt_token: UUID | None
    lease_expires_at: datetime | None


class AttemptEntity(Protocol):
    attempt_number: int
    attempt_token: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    error_code: str | None
    error_message: str | None
    provider: str | None
    model: str | None
    provider_response_id: str | None
    prompt_tokens: int | None
    cached_prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    estimated_cost_usd: Any | None
    latency_ms: int | None


class LegacyReportEntity(Protocol):
    id: UUID
    incident_id: UUID
    model: str
    content: dict[str, Any]
    created_at: datetime


class UnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    async def save_alerts(self, alerts: list[NormalizedAlert]) -> list[AlertEntity]: ...
    async def find_alert(self, alert_id: UUID) -> AlertEntity | None: ...
    async def lock_correlation_service(self, service: str) -> None: ...
    async def find_recent_open_incident(
        self, service: str, since: datetime
    ) -> IncidentEntity | None: ...
    async def find_open_incident_by_fingerprint(
        self, fingerprint: str
    ) -> IncidentEntity | None: ...
    async def create_incident(self, **values: Any) -> IncidentEntity: ...
    async def attach_alert(self, incident_id: UUID, alert_id: UUID) -> bool: ...
    async def latest_alert_statuses(self, incident_id: UUID) -> dict[str, str]: ...
    async def find_incident(
        self, incident_id: UUID, *, lock: bool = False
    ) -> IncidentEntity | None: ...
    async def list_incidents(self) -> list[IncidentEntity]: ...
    async def list_incident_alerts(self, incident_id: UUID) -> list[AlertEntity]: ...
    async def is_event_processed(self, consumer_name: str, event_id: UUID) -> bool: ...
    async def mark_event_processed(
        self, consumer_name: str, event_id: UUID
    ) -> None: ...
    async def add_outbox_event(
        self,
        *,
        event_id: UUID,
        topic: str,
        key: str,
        payload: dict[str, Any],
        available_at: datetime,
    ) -> None: ...
    async def create_investigation(self, **values: Any) -> InvestigationEntity: ...
    async def find_investigation(
        self, investigation_id: UUID, *, lock: bool = False
    ) -> InvestigationEntity | None: ...
    async def find_investigation_by_idempotency_key(
        self, incident_id: UUID, idempotency_key: str
    ) -> InvestigationEntity | None: ...
    async def find_active_investigation(
        self, incident_id: UUID, incident_revision: int, analyzer_version: str
    ) -> InvestigationEntity | None: ...
    async def list_investigations(
        self, incident_id: UUID
    ) -> list[InvestigationEntity]: ...
    async def create_attempt(self, **values: Any) -> AttemptEntity: ...
    async def find_attempt_by_token(self, token: UUID) -> AttemptEntity | None: ...
    async def list_attempts(self, investigation_id: UUID) -> list[AttemptEntity]: ...
    async def list_legacy_reports(
        self, incident_id: UUID
    ) -> list[LegacyReportEntity]: ...
    async def upsert_knowledge_document(
        self,
        *,
        service: str,
        environment: str,
        source: str,
        title: str,
        version: str,
        content_hash: str,
        embedding_model: str,
        embedding_dimensions: int,
        chunks: tuple[KnowledgeChunkRecord, ...],
    ) -> tuple[UUID, int]: ...
    async def delete_knowledge_document(self, document_id: UUID) -> bool: ...
    async def search_knowledge_chunks(
        self,
        *,
        service: str,
        environment: str,
        embedding_model: str,
        embedding_dimensions: int,
        embedding: tuple[float, ...],
        limit: int,
    ) -> list[KnowledgeEvidence]: ...


UnitOfWorkFactory = Callable[[], UnitOfWork]


class IncidentAnalyzer(Protocol):
    version: str
    provider: str
    model: str

    async def analyze(self, context: InvestigationContext) -> AnalysisOutput: ...


class EmbeddingProvider(Protocol):
    model: str

    async def embed(self, texts: list[str]) -> list[tuple[float, ...]]: ...


class KnowledgeRetriever(Protocol):
    async def retrieve(
        self, incident: IncidentSnapshot
    ) -> tuple[KnowledgeEvidence, ...]: ...
