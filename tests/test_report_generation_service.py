import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.core.errors import LLMProviderAppError, NotFoundAppError
from app.schemas.reports import ReportRead
from app.services.report_generation_service import ReportGenerationService


def test_generate_valid_report_persists_validated_content(
    monkeypatch,
    incident_id,
    incident_detail,
    valid_report_json,
    fake_prompt_renderer,
    llm_client_factory,
) -> None:
    llm_client = llm_client_factory(valid_report_json)
    persisted: dict[str, object] = {}

    def fake_load_incident(requested_id: UUID):
        assert requested_id == incident_id
        return incident_detail

    def fake_persist_report(
        requested_id: UUID,
        model: str,
        content,
    ) -> ReportRead:
        persisted["incident_id"] = requested_id
        persisted["model"] = model
        persisted["content"] = content
        return ReportRead(
            id=uuid4(),
            incident_id=requested_id,
            model=model,
            content=content,
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(
        ReportGenerationService,
        "_load_incident_detail",
        staticmethod(fake_load_incident),
    )
    monkeypatch.setattr(
        ReportGenerationService,
        "_persist_report",
        staticmethod(fake_persist_report),
    )

    service = ReportGenerationService(
        prompt_renderer=fake_prompt_renderer,
        llm_client=llm_client,
    )

    report = asyncio.run(service.generate(incident_id=incident_id))

    assert report.incident_id == incident_id
    assert report.model == "fake/test-model"
    assert report.content.summary == "The API stopped responding."
    assert persisted["content"] == report.content
    assert fake_prompt_renderer.received_incident == incident_detail
    assert llm_client.received_prompt == (
        f"Generate report for incident {incident_id}"
    )


def test_generate_rejects_invalid_llm_report(
    monkeypatch,
    incident_id,
    incident_detail,
    fake_prompt_renderer,
    llm_client_factory,
) -> None:
    llm_client = llm_client_factory('{"summary": "Incomplete report"}')

    monkeypatch.setattr(
        ReportGenerationService,
        "_load_incident_detail",
        staticmethod(lambda requested_id: incident_detail),
    )

    def fail_if_persisted(*args, **kwargs):
        pytest.fail("An invalid report must not be persisted")

    monkeypatch.setattr(
        ReportGenerationService,
        "_persist_report",
        staticmethod(fail_if_persisted),
    )

    service = ReportGenerationService(
        prompt_renderer=fake_prompt_renderer,
        llm_client=llm_client,
    )

    with pytest.raises(LLMProviderAppError) as exc_info:
        asyncio.run(service.generate(incident_id=incident_id))

    assert exc_info.value.code == "llm_invalid_report"
    assert exc_info.value.metadata == {
        "operation": "validate_report_content",
        "incident_id": str(incident_id),
    }


def test_generate_stops_when_incident_does_not_exist(
    monkeypatch,
    incident_id,
    fake_prompt_renderer,
    valid_report_json,
    llm_client_factory,
) -> None:
    llm_client = llm_client_factory(valid_report_json)

    def raise_not_found(requested_id: UUID):
        raise NotFoundAppError(
            message="Incident not found",
            metadata={"incident_id": str(requested_id)},
        )

    monkeypatch.setattr(
        ReportGenerationService,
        "_load_incident_detail",
        staticmethod(raise_not_found),
    )

    service = ReportGenerationService(
        prompt_renderer=fake_prompt_renderer,
        llm_client=llm_client,
    )

    with pytest.raises(NotFoundAppError):
        asyncio.run(service.generate(incident_id=incident_id))

    assert llm_client.call_count == 0
    assert fake_prompt_renderer.received_incident is None
