from pprint import pprint
from typing import Any

from fastapi import APIRouter

from app.schemas.grafana import GrafanaWebhookPayload


router = APIRouter(prefix="/webhooks/grafana", tags=["grafana"])

@router.post("")
def receive_grafana_webhook(payload: GrafanaWebhookPayload) -> dict[str, object]:
    return {
        "status": "accepted",
        "source": "grafana",
        "alerts_received": len(payload.alerts),
        "group_key": payload.groupKey,
    }
