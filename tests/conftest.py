import hashlib
import hmac
import json
from collections.abc import Callable, Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from vigilia.adapters.http import security as security_module
from vigilia.adapters.http.dependencies import get_application
from vigilia.adapters.http.errors import register_exception_handlers
from vigilia.adapters.http.routes import router
from vigilia.application.contracts import AlertIngestionResult
from vigilia.bootstrap.settings import Settings


TEST_GRAFANA_SECRET = "test-grafana-hmac-secret"
TEST_API_TOKEN = "test-api-token"
FIXED_NOW = 1_750_000_000


class FakeIngestAlerts:
    def __init__(self) -> None:
        self.alerts = None
        self.alerts_received = None

    async def execute(self, alerts, alerts_received: int) -> AlertIngestionResult:
        self.alerts = alerts
        self.alerts_received = alerts_received
        return AlertIngestionResult(
            alerts_received=alerts_received,
            alerts_normalized=len(alerts),
            alerts_persisted=len(alerts),
            events_queued=len(alerts),
        )


class FakeIncidentQueries:
    async def list(self) -> list:
        return []


@pytest.fixture
def application() -> SimpleNamespace:
    return SimpleNamespace(
        settings=Settings(
            _env_file=None,
            api_token=None,
            grafana_webhook_hmac_secret=None,
        ),
        ingest_alerts=FakeIngestAlerts(),
        incident_queries=FakeIncidentQueries(),
    )


@pytest.fixture
def client(application: SimpleNamespace) -> Generator[TestClient]:
    app = FastAPI()
    app.state.vigilia = application
    app.dependency_overrides[get_application] = lambda: application
    register_exception_handlers(app)
    app.include_router(router)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def grafana_payload() -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "grafana_notification_test.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def configured_grafana_security(application, monkeypatch) -> None:
    application.settings.grafana_webhook_hmac_secret = SecretStr(TEST_GRAFANA_SECRET)
    monkeypatch.setattr(security_module.time, "time", lambda: FIXED_NOW)


@pytest.fixture
def configured_api_security(application) -> None:
    application.settings.api_token = SecretStr(TEST_API_TOKEN)


@pytest.fixture
def api_authorization_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_API_TOKEN}"}


@pytest.fixture
def signed_grafana_request() -> Callable:
    def build_request(
        payload: dict, *, timestamp: str | None = None
    ) -> tuple[bytes, dict[str, str]]:
        body = json.dumps(
            payload, separators=(",", ":"), ensure_ascii=False
        ).encode()
        request_timestamp = timestamp or str(FIXED_NOW)
        signed_payload = request_timestamp.encode() + b":" + body
        signature = hmac.new(
            TEST_GRAFANA_SECRET.encode(), signed_payload, hashlib.sha256
        ).hexdigest()
        return body, {
            "Content-Type": "application/json",
            "X-Grafana-Alerting-Signature": signature,
            "X-Grafana-Alerting-Timestamp": request_timestamp,
        }

    return build_request
