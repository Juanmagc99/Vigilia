from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class OutboxEvent(SQLModel, table=True):
    __tablename__ = "outbox_events"  # type: ignore

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    topic: str = Field(index=True)
    key: str
    payload: dict[str, Any] = Field(
        sa_column=Column(JSONB, nullable=False),
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )
    published_at: datetime | None = Field(default=None, index=True)
    available_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )
    locked_until: datetime | None = Field(default=None, index=True)
    claim_token: UUID | None = Field(default=None, index=True)
    attempts: int = 0
    last_error: str | None = None
