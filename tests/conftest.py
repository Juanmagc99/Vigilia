import hashlib
import hmac
import json
from collections.abc import Callable, Generator
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import app.api.security as security_module
from app.core.config import settings
from app.db.models.alert import Alert
from app.main import app
from app.schemas.incidents import IncidentDetail
from app.schemas.reports import ReportContent


TEST_GRAFANA_SECRET = "test-grafana-hmac-secret"
TEST_API_TOKEN = "test-api-token"
FIXED_NOW = 1_750_000_000


@pytest.fixture
def client() -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def incident_id() -> UUID:
    return uuid4()


@pytest.fixture
def incident_detail(incident_id: UUID) -> IncidentDetail:
    now = datetime.now(timezone.utc)

    return IncidentDetail(
        id=incident_id,
        status="resolved",
        service="payments",
        severity="critical",
        title="Payments unavailable",
        started_at=now,
        updated_at=now,
        resolved_at=now,
        alerts=[],
    )


@pytest.fixture
def valid_report_content() -> ReportContent:
    return ReportContent(
        summary="The API stopped responding.",
        probable_cause="Database connection pool exhaustion.",
        impact="HTTP 500 responses for five minutes.",
        timeline=[
            {
                "timestamp": "2026-07-23T10:00:00Z",
                "event": "Errors started",
            }
        ],
        recommended_actions=["Review the database connection pool"],
        missing_information=[],
        confidence=0.85,
    )


@pytest.fixture
def valid_report_json(valid_report_content: ReportContent) -> str:
    return valid_report_content.model_dump_json()


@pytest.fixture
def grafana_payload() -> dict:
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "grafana_notification_test.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def configured_grafana_security(monkeypatch) -> None:
    monkeypatch.setattr(
        settings,
        "grafana_webhook_hmac_secret",
        SecretStr(TEST_GRAFANA_SECRET),
    )
    monkeypatch.setattr(
        settings,
        "grafana_webhook_max_age_seconds",
        300,
    )
    monkeypatch.setattr(
        security_module.time,
        "time",
        lambda: FIXED_NOW,
    )


@pytest.fixture
def configured_api_security(monkeypatch) -> None:
    monkeypatch.setattr(
        settings,
        "api_token",
        SecretStr(TEST_API_TOKEN),
    )


@pytest.fixture
def api_authorization_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_API_TOKEN}"}


@pytest.fixture
def signed_grafana_request() -> Callable:
    def build_request(
        payload: dict,
        *,
        timestamp: str | None = None,
        secret: str = TEST_GRAFANA_SECRET,
        body_to_sign: bytes | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        body = json.dumps(
            payload,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        request_timestamp = timestamp or str(FIXED_NOW)
        signed_body = body if body_to_sign is None else body_to_sign
        signed_payload = request_timestamp.encode("utf-8") + b":" + signed_body
        signature = hmac.new(
            key=secret.encode("utf-8"),
            msg=signed_payload,
            digestmod=hashlib.sha256,
        ).hexdigest()

        return body, {
            "Content-Type": "application/json",
            "X-Grafana-Alerting-Signature": signature,
            "X-Grafana-Alerting-Timestamp": request_timestamp,
        }

    return build_request


class FakePromptRenderer:
    def __init__(self) -> None:
        self.received_incident: IncidentDetail | None = None

    def render_incident_report(self, incident: IncidentDetail) -> str:
        self.received_incident = incident
        return f"Generate report for incident {incident.id}"


@pytest.fixture
def fake_prompt_renderer() -> FakePromptRenderer:
    return FakePromptRenderer()


class FakeLLMClient:
    def __init__(self, response: str, model: str = "fake/test-model") -> None:
        self.response = response
        self.model = model
        self.received_prompt: str | None = None
        self.call_count = 0

    async def generate(self, *, prompt: str) -> str:
        self.call_count += 1
        self.received_prompt = prompt
        return self.response


@pytest.fixture
def llm_client_factory() -> Callable[[str], FakeLLMClient]:
    return FakeLLMClient


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commit_called = False
        self.rollback_called = False
        self.refreshed: list[object] = []

    def add_all(self, instances: list[object]) -> None:
        self.added.extend(instances)

    def commit(self) -> None:
        self.commit_called = True

    def rollback(self) -> None:
        self.rollback_called = True

    def refresh(self, instance: object) -> None:
        self.refreshed.append(instance)


@pytest.fixture
def fake_session() -> FakeSession:
    return FakeSession()

