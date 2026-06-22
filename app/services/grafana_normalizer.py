from app.schemas.alerts import NormalizedAlert
from app.schemas.grafana import GrafanaAlert, GrafanaWebhookPayload


def normalize_grafana_payload(payload: GrafanaWebhookPayload) -> list[NormalizedAlert]:
    return [_normalize_alert(alert, payload) for alert in payload.alerts]


def _normalize_alert(
    alert: GrafanaAlert, payload: GrafanaWebhookPayload
) -> NormalizedAlert:
    labels = dict(alert.labels)
    annotations = dict(alert.annotations)

    return NormalizedAlert(
        alert_id=alert.fingerprint,
        source="grafana",
        fingerprint=alert.fingerprint,
        status=alert.status,
        alert_name=labels.get("alertname"),
        service=labels.get("service") or labels.get("instance") or "unknown",
        severity=labels.get("severity") or "unknown",
        summary=annotations.get("summary") or payload.title,
        description=annotations.get("description"),
        labels=labels,
        annotations=annotations,
        starts_at=alert.startsAt,
        ends_at=alert.endsAt,
        dashboard_url=alert.dashboardURL or None,
        panel_url=alert.panelURL or None,
        silence_url=alert.silenceURL or None
    )


def _empty_to_none(value: str | None) -> str | None:
    if value == "":
        return None
    return value
