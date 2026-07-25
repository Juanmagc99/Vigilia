import json
from collections.abc import Callable, Generator
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models.alert import Alert
from app.main import app
from app.schemas.incidents import IncidentDetail
from app.schemas.reports import ReportContent


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


class FakeAlertEventPublisher:
    def __init__(self) -> None:
        self.published_alerts: list[Alert] = []

    def publish_alert_received(self, alert: Alert) -> None:
        self.published_alerts.append(alert)


@pytest.fixture
def fake_alert_publisher() -> FakeAlertEventPublisher:
    return FakeAlertEventPublisher()
