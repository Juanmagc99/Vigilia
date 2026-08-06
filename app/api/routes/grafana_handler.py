from fastapi import APIRouter, Depends, status

from app.api.security import verify_grafana_signature
from app.db.session import DatabaseSession
from app.schemas.grafana import GrafanaWebhookPayload
from app.services.alert_ingestion_service import ingest_grafana_payload


router = APIRouter(
    prefix="/webhooks/grafana",
    tags=["grafana"],
    dependencies=[Depends(verify_grafana_signature)],
)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def receive_grafana_webhook(
    payload: GrafanaWebhookPayload,
    session: DatabaseSession,
) -> dict[str, object]:
    result = ingest_grafana_payload(
        payload=payload,
        session=session,
    )

    return {
        "status": "accepted",
        "source": "grafana",
        "alerts_received": result.alerts_received,
        "alerts_normalized": result.alerts_normalized,
        "alerts_persisted": result.alerts_persisted,
        "events_queued": result.events_queued,
        "group_key": payload.groupKey,
    }
