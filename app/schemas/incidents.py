from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.alerts import AlertRead


class IncidentSummary(BaseModel):
    id: UUID
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
