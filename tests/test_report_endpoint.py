from datetime import datetime, timezone
from uuid import uuid4

from app.api.routes.incident_handler import get_report_generation_service
from app.main import app
from app.schemas.reports import ReportRead


def test_generate_report_returns_error_when_llm_is_not_configured(
    client,
) -> None:
    app.state.report_generation_service = None
    incident_id = uuid4()

    response = client.post(f"/incidents/{incident_id}/report")

    assert response.status_code == 500
    assert response.json()["error"]["type"] == "internal_error"
    assert response.json()["error"]["code"] == "llm_not_configured"


def test_generate_report_returns_generated_report(
    client,
    incident_id,
    valid_report_content,
) -> None:
    expected_report = ReportRead(
        id=uuid4(),
        incident_id=incident_id,
        model="fake/test-model",
        content=valid_report_content,
        created_at=datetime.now(timezone.utc),
    )

    class FakeReportGenerationService:
        async def generate(self, *, incident_id):
            return expected_report

    app.dependency_overrides[get_report_generation_service] = (
        FakeReportGenerationService
    )

    response = client.post(f"/incidents/{incident_id}/report")

    assert response.status_code == 200
    assert response.json()["id"] == str(expected_report.id)
    assert response.json()["incident_id"] == str(incident_id)
    assert response.json()["content"]["confidence"] == 0.85
