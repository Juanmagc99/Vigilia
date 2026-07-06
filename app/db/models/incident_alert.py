from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Field, SQLModel


class IncidentAlert(SQLModel, table=True):
    __tablename__ = "incident_alerts" # type: ignore

    incident_id: UUID = Field(
        foreign_key="incidents.id",
        primary_key=True,
    )
    alert_id: UUID = Field(
        foreign_key="alerts.id",
        primary_key=True,
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )