from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AlertReceivedMessage(BaseModel):
    event_type: str = "AlertReceived"
    alert_id: UUID
    source: str
    fingerprint: str
    status: str
    alert_name: str | None
    service: str
    severity: str
    starts_at: datetime
    received_at: datetime