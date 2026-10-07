"""Exercise the running API, outbox and worker with unique synthetic data."""

import argparse
from http.client import RemoteDisconnected
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from send_grafana_alert import build_payload, post_json
from vigilia.bootstrap.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--timeout", type=float, default=45)
    args = parser.parse_args()
    settings = Settings()
    if settings.investigation_analyzer != "simulated" or settings.rag_enabled:
        raise SystemExit(
            "Smoke requires simulated analysis and RAG disabled in .env and all "
            "running processes. Restart them after changing configuration."
        )
    if not settings.api_token or not settings.grafana_webhook_hmac_secret:
        raise SystemExit("Configure the API token and Grafana HMAC secret first.")
    base = args.api_url.rstrip("/")
    token = settings.api_token.get_secret_value()

    def request(path, *, method="GET", body=None, key=None):
        headers = {"Authorization": f"Bearer {token}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if key:
            headers["Idempotency-Key"] = key
        req = Request(
            base + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        with urlopen(req, timeout=10) as response:
            return response.status, json.load(response)

    def wait_for(read, predicate, label):
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            value = read()
            if predicate(value):
                return value
            time.sleep(0.5)
        raise RuntimeError(f"Timed out waiting for {label}")

    def ready():
        try:
            return request("/ready")[0] == 200
        except (URLError, RemoteDisconnected, TimeoutError):
            return False

    wait_for(ready, bool, "API readiness")
    assert request("/health")[0] == 200
    with urlopen(base + "/ui/", timeout=10) as response:
        assert b"/ui/app.js" in response.read()
    try:
        urlopen(base + "/incidents", timeout=10)
    except HTTPError as exc:
        assert exc.code == 401
    else:
        raise AssertionError("Incident data must require authentication")

    service = f"smoke-{uuid4().hex[:12]}"
    fingerprint = uuid4().hex
    payload = build_payload(service, "firing", "critical", "SmokeAlert", service, fingerprint)
    webhook = base + "/webhooks/grafana"
    secret = settings.grafana_webhook_hmac_secret.get_secret_value()
    status, accepted = post_json(webhook, payload, hmac_secret=secret)
    assert status == 202 and json.loads(accepted)["events_queued"] == 1
    status, duplicate = post_json(webhook, payload, hmac_secret=secret)
    assert status == 202 and json.loads(duplicate)["events_queued"] == 0
    page = wait_for(
        lambda: request(f"/alerts?service={service}")[1],
        lambda value: bool(value["items"] and value["items"][0]["incident_id"]),
        "alert correlation",
    )
    assert page["total"] == 1
    incident_id = page["items"][0]["incident_id"]
    detail = request(f"/incidents/{incident_id}")[1]
    assert detail["status"] == "open" and detail["revision"] == 1
    key = uuid4().hex
    path = f"/incidents/{incident_id}/investigations"
    status, investigation = request(path, method="POST", key=key)
    assert status == 202 and investigation["analyzer_version"] == "simulated-v1"
    replay = request(path, method="POST", key=key)[1]
    assert replay["id"] == investigation["id"]
    result = wait_for(
        lambda: request(f"/investigations/{investigation['id']}")[1],
        lambda value: value["status"] in ("completed", "failed"),
        "investigation completion",
    )
    assert result["status"] == "completed", result.get("error_code")
    assert result["result_schema"] == "incident_investigation.v1"
    assert result["attempt_count"] == 1 and result["attempts"][0]["provider"] == "simulation"
    assert result["result"]["evidence"][0]["id"] == f"alert:{page['items'][0]['id']}"
    assert len(request(path)[1]) == 1
    knowledge = request("/knowledge/documents?limit=1")[1]
    assert {"items", "total", "limit", "offset"} <= knowledge.keys()
    payload["status"] = "resolved"
    payload["alerts"][0]["status"] = "resolved"
    payload["alerts"][0]["annotations"]["summary"] = f"SmokeAlert is resolved for {service}"
    payload["alerts"][0]["endsAt"] = payload["alerts"][0]["startsAt"]
    assert post_json(webhook, payload, hmac_secret=secret)[0] == 202
    closed = wait_for(
        lambda: request(f"/incidents/{incident_id}")[1],
        lambda value: value["status"] == "resolved",
        "incident resolution",
    )
    assert closed["revision"] == 2 and len(closed["alerts"]) == 2
    print(f"Smoke passed: alert -> outbox -> incident -> investigation -> resolved ({service})")


if __name__ == "__main__":
    main()
