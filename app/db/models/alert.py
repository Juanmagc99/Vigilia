from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Alert(SQLModel, table=True):
    __tablename__ = "alerts" # type: ignore

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    source: str
    fingerprint: str
    status: str

    alert_name: str | None = None
    service: str
    severity: str

    summary: str | None = None
    description: str | None = None

    labels: dict[str, str] = Field(sa_column=Column(JSONB, nullable=False))
    annotations: dict[str, str] = Field(sa_column=Column(JSONB, nullable=False))

    starts_at: datetime
    ends_at: datetime | None = None
    received_at: datetime

    dashboard_url: str | None = None
    panel_url: str | None = None
    silence_url: str | None = None