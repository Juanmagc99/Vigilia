from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class GrafanaAlert(BaseModel):
    status: Literal["firing", "resolved"]
    labels: dict[str, str]
    annotations: dict[str, str] = {}
    startsAt: datetime
    endsAt: datetime | None = None
    fingerprint: str
    generatorURL: str | None = None
    silenceURL: str | None = None
    dashboardURL: str | None = None
    panelURL: str | None = None
    valueString: str | None = None
    values: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")


class GrafanaWebhookPayload(BaseModel):
    receiver: str
    status: Literal["firing", "resolved"]
    orgId: int
    alerts: list[GrafanaAlert]
    groupLabels: dict[str, str] = {}
    commonLabels: dict[str, str] = {}
    commonAnnotations: dict[str, str] = {}
    externalURL: str | None = None
    version: str
    groupKey: str
    truncatedAlerts: int = 0
    title: str | None = None
    state: str | None = None
    message: str | None = None
    appVersion: str | None = None

    model_config = ConfigDict(extra="allow")
