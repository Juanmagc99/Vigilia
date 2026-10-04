def test_webhook_normalizes_and_queues_grafana_alerts(
    client,
    application,
    grafana_payload,
    configured_grafana_security,
    signed_grafana_request,
) -> None:
    body, headers = signed_grafana_request(grafana_payload)

    response = client.post("/webhooks/grafana", content=body, headers=headers)

    assert response.status_code == 202
    assert response.json()["alerts_received"] == 1
    assert response.json()["alerts_normalized"] == 1
    assert response.json()["events_queued"] == 1
    assert application.ingest_alerts.alerts[0].fingerprint == "57c6d9296de2ad39"


def test_webhook_rejects_invalid_signature_before_ingestion(
    client,
    application,
    grafana_payload,
    configured_grafana_security,
    signed_grafana_request,
) -> None:
    body, headers = signed_grafana_request(grafana_payload)
    headers["X-Grafana-Alerting-Signature"] = "0" * 64

    response = client.post("/webhooks/grafana", content=body, headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_grafana_signature"
    assert application.ingest_alerts.alerts is None
