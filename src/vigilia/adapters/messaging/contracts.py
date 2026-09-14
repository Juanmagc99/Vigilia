from pydantic import BaseModel

from vigilia.application.contracts import EventEnvelope


class IncomingEvent(BaseModel):
    envelope: EventEnvelope
    topic: str
    partition: int
    offset: int
