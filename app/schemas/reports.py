from pydantic import BaseModel, Field


class TimelineEntry(BaseModel):
    timestamp: str | None = None
    event: str


class IncidentReport(BaseModel):
    summary: str
    probable_cause: str | None = None
    impact: str
    timeline: list[TimelineEntry]
    recommended_actions: list[str]
    missing_information: list[str]
    confidence: float = Field(ge=0.0, le=1.0)