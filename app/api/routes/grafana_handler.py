from fastapi import APIRouter

from app.db.session import DatabaseSession
from app.repositories.alert_repository import save_alerts
from app.schemas.grafana import GrafanaWebhookPayload
from app.services.grafana_normalizer import normalize_grafana_payload


router = APIRouter(prefix="/webhooks/grafana", tags=["grafana"])

@router.post("")
def receive_grafana_webhook(
    payload: GrafanaWebhookPayload, session: DatabaseSession
) -> dict[str, object]:
    norm_alerts = normalize_grafana_payload(payload)
    saved_alerts = save_alerts(session, norm_alerts)

    return {
        "status": "accepted",
        "source": "grafana",
        "alerts_received": len(payload.alerts),
        "alerts_normalized": len(norm_alerts),
        "alerts_persisted": len(saved_alerts),
        "group_key": payload.groupKey,
    }
