from fastapi import APIRouter

from app.db.session import DatabaseSession
from app.events.publisher import AlertEventPublisherDependency
from app.schemas.grafana import GrafanaWebhookPayload
from app.services.alert_ingestion_service import ingest_grafana_payload


router = APIRouter(prefix="/webhooks/grafana", tags=["grafana"])


@router.post("")
def receive_grafana_webhook(
    payload: GrafanaWebhookPayload,
    session: DatabaseSession,
    publisher: AlertEventPublisherDependency,
) -> dict[str, object]:
    result = ingest_grafana_payload(
        payload=payload,
        session=session,
        publisher=publisher,
    )

    return {
        "status": "accepted",
        "source": "grafana",
        "alerts_received": result.alerts_received,
        "alerts_normalized": result.alerts_normalized,
        "alerts_persisted": result.alerts_persisted,
        "events_published": result.events_published,
        "group_key": payload.groupKey,
    }