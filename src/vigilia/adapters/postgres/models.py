from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AlertModel(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "fingerprint",
            "starts_at",
            "status",
            name="uq_alert_source_fingerprint_starts_at_status",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    alert_name: Mapped[str | None] = mapped_column(String)
    service: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String)
    labels: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    annotations: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    dashboard_url: Mapped[str | None] = mapped_column(String)
    panel_url: Mapped[str | None] = mapped_column(String)
    silence_url: Mapped[str | None] = mapped_column(String)


class IncidentModel(Base):
    __tablename__ = "incidents"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    service: Mapped[str] = mapped_column(String, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class IncidentAlertModel(Base):
    __tablename__ = "incident_alerts"
    incident_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("incidents.id"), primary_key=True
    )
    alert_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("alerts.id"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class OutboxEventModel(Base):
    __tablename__ = "outbox_events"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    topic: Mapped[str] = mapped_column(String, nullable=False, index=True)
    key: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    claim_token: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String)


class ReportModel(Base):
    __tablename__ = "reports"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    incident_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("incidents.id"), index=True
    )
    model: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class InvestigationModel(Base):
    __tablename__ = "investigations"
    __table_args__ = (
        Index(
            "uq_investigations_active_revision_analyzer",
            "incident_id",
            "incident_revision",
            "analyzer_version",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running', 'retry_wait')"),
        ),
        Index(
            "uq_investigations_incident_idempotency_key",
            "incident_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("ix_investigations_pending", "status", "next_attempt_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    incident_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("incidents.id"), nullable=False, index=True
    )
    incident_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    analyzer_version: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_schema: Mapped[str | None] = mapped_column(String)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String)
    error_message: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    attempt_token: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )


class InvestigationAttemptModel(Base):
    __tablename__ = "investigation_attempts"
    __table_args__ = (
        Index(
            "uq_investigation_attempt_number",
            "investigation_id",
            "attempt_number",
            unique=True,
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    investigation_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_token: Mapped[UUID] = mapped_column(Uuid, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String)
    error_message: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String)
    model: Mapped[str | None] = mapped_column(String)
    provider_response_id: Mapped[str | None] = mapped_column(String)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    cached_prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 8))
    latency_ms: Mapped[int | None] = mapped_column(Integer)


class ProcessedEventModel(Base):
    __tablename__ = "processed_events"
    consumer_name: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
