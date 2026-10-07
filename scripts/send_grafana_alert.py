from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from vigilia.bootstrap.settings import Settings

DEFAULT_WEBHOOK_URL = "http://localhost:8000/webhooks/grafana"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a Grafana-like alert webhook to Vigilia."
    )
    parser.add_argument("--service", required=True)
    parser.add_argument("--status", required=True, choices=["firing", "resolved"])
    parser.add_argument("--severity", required=True)
    parser.add_argument("--alert-name", default="SyntheticAlert")
    parser.add_argument("--instance", default=None)
    parser.add_argument("--fingerprint", default=None)
    parser.add_argument("--webhook-url", default=DEFAULT_WEBHOOK_URL)
    parser.add_argument(
        "--hmac-secret",
        default=get_configured_hmac_secret(),
        help=(
            "Grafana webhook HMAC secret. Defaults to "
            "VIGILIA_GRAFANA_WEBHOOK_HMAC_SECRET."
        ),
    )

    args = parser.parse_args()

    if args.hmac_secret is None:
        parser.error(
            "Configure VIGILIA_GRAFANA_WEBHOOK_HMAC_SECRET "
            "or provide --hmac-secret."
        )

    instance = args.instance or args.service
    fingerprint = args.fingerprint or build_fingerprint(
        service=args.service,
        alert_name=args.alert_name,
        instance=instance,
    )

    payload = build_payload(
        service=args.service,
        status=args.status,
        severity=args.severity,
        alert_name=args.alert_name,
        instance=instance,
        fingerprint=fingerprint,
    )

    response_status, response_body = post_json(
        args.webhook_url,
        payload,
        hmac_secret=args.hmac_secret,
    )

    print(f"Sent alert status={args.status}")
    print(f"service={args.service}")
    print(f"severity={args.severity}")
    print(f"alert_name={args.alert_name}")
    print(f"fingerprint={fingerprint}")
    print(f"webhook_status={response_status}")
    print(response_body)


def build_fingerprint(service: str, alert_name: str, instance: str) -> str:
    raw_value = f"{service}:{alert_name}:{instance}".encode("utf-8")
    return hashlib.sha256(raw_value).hexdigest()[:16]


def get_configured_hmac_secret() -> str | None:
    secret = Settings().grafana_webhook_hmac_secret
    return secret.get_secret_value() if secret else None


def build_hmac_signature(
    *,
    hmac_secret: str,
    timestamp: str,
    body: bytes,
) -> str:
    signed_payload = timestamp.encode("utf-8") + b":" + body

    return hmac.new(
        key=hmac_secret.encode("utf-8"),
        msg=signed_payload,
        digestmod=hashlib.sha256,
    ).hexdigest()


def build_payload(
    service: str,
    status: str,
    severity: str,
    alert_name: str,
    instance: str,
    fingerprint: str,
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat().replace("+00:00", "Z")

    labels = {
        "alertname": alert_name,
        "service": service,
        "instance": instance,
        "severity": severity,
    }
    annotations = {
        "summary": f"{alert_name} is {status} for {service}",
        "description": "Synthetic alert generated from scripts/send_grafana_alert.py",
    }

    return {
        "receiver": "vigilia-synthetic",
        "status": status,
        "orgId": 1,
        "alerts": [
            {
                "status": status,
                "labels": labels,
                "annotations": annotations,
                "startsAt": now_iso,
                "endsAt": now_iso if status == "resolved" else None,
                "fingerprint": fingerprint,
                "generatorURL": "http://localhost:3000/synthetic-alert",
                "silenceURL": "",
                "dashboardURL": "",
                "panelURL": "",
                "valueString": "[ synthetic=true value=1 ]",
                "values": {"synthetic": 1},
            }
        ],
        "groupLabels": {
            "alertname": alert_name,
            "service": service,
        },
        "commonLabels": labels,
        "commonAnnotations": annotations,
        "externalURL": "http://localhost:3000/",
        "version": "1",
        "groupKey": f"synthetic-{fingerprint}",
        "truncatedAlerts": 0,
        "title": f"[{status.upper()}:1] {alert_name} {service}",
        "state": "alerting" if status == "firing" else "ok",
        "message": f"{status.upper()} {alert_name} for {service}",
        "appVersion": "synthetic",
    }


def post_json(
    url: str,
    payload: dict[str, object],
    *,
    hmac_secret: str,
) -> tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = build_hmac_signature(
        hmac_secret=hmac_secret,
        timestamp=timestamp,
        body=body,
    )

    request = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Grafana-Alerting-Signature": signature,
            "X-Grafana-Alerting-Timestamp": timestamp,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            return response.status, body
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, body
    except URLError as exc:
        raise SystemExit(f"Could not send alert to {url}: {exc}") from exc


if __name__ == "__main__":
    main()
