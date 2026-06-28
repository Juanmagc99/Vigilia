from pprint import pprint
from typing import Any

from fastapi import APIRouter

from app.schemas.grafana import GrafanaWebhookPayload
from app.services.grafana_normalizer import normalize_grafana_payload


router = APIRouter(prefix="/webhooks/grafana", tags=["grafana"])

@router.post("")
def receive_grafana_webhook(payload: GrafanaWebhookPayload) -> dict[str, object]:
    norm_alerts = normalize_grafana_payload(payload)

    return {
        "status": "accepted",
        "source": "grafana",
        "alerts_received": len(payload.alerts),
        "alerts_normalized": len(norm_alerts),
        "group_key": payload.groupKey,
    }
