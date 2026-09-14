from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID


class AlertStatus(StrEnum):
    FIRING = "firing"
    RESOLVED = "resolved"


class IncidentStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class InvestigationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    COMPLETED = "completed"
    FAILED = "failed"


ACTIVE_INVESTIGATION_STATUSES = (
    InvestigationStatus.QUEUED,
    InvestigationStatus.RUNNING,
    InvestigationStatus.RETRY_WAIT,
)


@dataclass(frozen=True)
class NormalizedAlert:
    source: str
    fingerprint: str
    status: AlertStatus
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


@dataclass(frozen=True)
class AlertEvidence:
    id: UUID
    fingerprint: str
    status: str
    alert_name: str | None
    service: str
    severity: str
    summary: str | None
    description: str | None
    starts_at: datetime
    ends_at: datetime | None
    received_at: datetime


@dataclass(frozen=True)
class IncidentSnapshot:
    id: UUID
    revision: int
    status: str
    service: str
    severity: str
    title: str
    started_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    alerts: tuple[AlertEvidence, ...]


@dataclass(frozen=True)
class KnowledgeEvidence:
    id: UUID
    document_id: UUID
    service: str
    title: str
    content: str
    version: str


@dataclass(frozen=True)
class InvestigationContext:
    incident: IncidentSnapshot
    knowledge: tuple[KnowledgeEvidence, ...] = ()


@dataclass(frozen=True)
class AnalysisResult:
    schema: str
    outcome: str
    summary: str
    hypotheses: tuple[dict[str, Any], ...]
    evidence: tuple[dict[str, Any], ...]
    recommended_checks: tuple[str, ...]
    missing_information: tuple[str, ...]

    def as_json(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "outcome": self.outcome,
            "summary": self.summary,
            "hypotheses": list(self.hypotheses),
            "evidence": list(self.evidence),
            "recommended_checks": list(self.recommended_checks),
            "missing_information": list(self.missing_information),
        }


@dataclass(frozen=True)
class AnalysisUsage:
    provider: str
    model: str
    response_id: str | None
    prompt_tokens: int | None
    cached_prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    estimated_cost_usd: Decimal | None
    latency_ms: int


@dataclass(frozen=True)
class AnalysisOutput:
    result: AnalysisResult
    usage: AnalysisUsage
