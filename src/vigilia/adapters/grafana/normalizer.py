from datetime import UTC, datetime

from vigilia.adapters.grafana.schemas import GrafanaAlert, GrafanaWebhookPayload
from vigilia.domain.models import AlertStatus, NormalizedAlert


def normalize_grafana_payload(payload: GrafanaWebhookPayload) -> list[NormalizedAlert]:
    received_at = datetime.now(UTC)
    return [_normalize_alert(alert, payload, received_at) for alert in payload.alerts]


def _normalize_alert(
    alert: GrafanaAlert, payload: GrafanaWebhookPayload, received_at: datetime
) -> NormalizedAlert:
    labels = dict(alert.labels)
    annotations = dict(alert.annotations)
    return NormalizedAlert(
        source="grafana",
        fingerprint=alert.fingerprint,
        status=AlertStatus(alert.status),
        alert_name=labels.get("alertname"),
        service=labels.get("service") or labels.get("instance") or "unknown",
        severity=labels.get("severity") or "unknown",
        summary=annotations.get("summary") or payload.title,
        description=annotations.get("description"),
        labels=labels,
        annotations=annotations,
        starts_at=alert.startsAt,
        ends_at=alert.endsAt,
        received_at=received_at,
        dashboard_url=alert.dashboardURL or None,
        panel_url=alert.panelURL or None,
        silence_url=alert.silenceURL or None,
    )
