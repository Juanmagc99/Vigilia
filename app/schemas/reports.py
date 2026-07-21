from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TimelineEntry(BaseModel):
    timestamp: str | None = None
    event: str


class ReportContent(BaseModel):
    summary: str
    probable_cause: str | None = None
    impact: str
    timeline: list[TimelineEntry]
    recommended_actions: list[str]
    missing_information: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class ReportRead(BaseModel):
    id: UUID
    incident_id: UUID
    model: str
    content: ReportContent
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
