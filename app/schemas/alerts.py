from datetime import UTC, datetime

from pydantic import BaseModel, Field


class NormalizedAlert(BaseModel):
    alert_id: str
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
    dashboard_url: str | None = None
    panel_url: str | None = None
    silence_url: str | None = None
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
