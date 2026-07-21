
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Report(SQLModel, table=True):
    __tablename__ = "reports"  # type: ignore

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    incident_id: UUID = Field(foreign_key="incidents.id", index=True)

    model: str
    content: dict = Field(sa_column=Column(JSONB, nullable=False))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
