from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class Incident(SQLModel, table=True):
    __tablename__ = "incidents" # type: ignore

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    status: str = Field(index=True)
    service: str = Field(index=True)
    severity: str
    title: str

    started_at: datetime
    updated_at: datetime = Field(index=True)
    resolved_at: datetime | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    ) 