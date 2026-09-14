from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class AlertRead(BaseModel):
    id: UUID
    source: str
    fingerprint: str
    status: str
    alert_name: str | None = None
    service: str
    severity: str
    summary: str | None = None
    description: str | None = None
    labels: dict[str, str]
    annotations: dict[str, str]
    starts_at: datetime
    ends_at: datetime | None = None
    received_at: datetime
    dashboard_url: str | None = None
    panel_url: str | None = None
    silence_url: str | None = None
    model_config = ConfigDict(from_attributes=True)


class IncidentSummary(BaseModel):
    id: UUID
    revision: int
    status: str
    service: str
    severity: str
    title: str
    started_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class IncidentDetail(IncidentSummary):
    alerts: list[AlertRead]


class InvestigationAttemptRead(BaseModel):
    attempt_number: int
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
    estimated_cost_usd: Decimal | None
    latency_ms: int | None
    model_config = ConfigDict(from_attributes=True)


class InvestigationRead(BaseModel):
    id: UUID
    incident_id: UUID
    incident_revision: int
    analyzer_version: str
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
    attempts: list[InvestigationAttemptRead] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class LegacyReportRead(BaseModel):
    id: UUID
    incident_id: UUID
    model: str
    content: dict[str, Any]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AlertIngestionResult(BaseModel):
    alerts_received: int
    alerts_normalized: int
    alerts_persisted: int
    events_queued: int


class EventEnvelope(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    aggregate_id: UUID
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID
    causation_id: UUID | None = None
    payload: dict[str, Any]
