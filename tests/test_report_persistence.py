from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

import app.services.report_generation_service as report_module
from app.core.errors import DatabaseAppError
from app.services.report_generation_service import ReportGenerationService


def test_persist_report_rolls_back_on_database_error(
    monkeypatch,
    valid_report_content,
) -> None:
    session_state = {
        "commit_called": False,
        "rollback_called": False,
    }

    class FailingSession:
        def __init__(self, engine) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            pass

        def commit(self) -> None:
            session_state["commit_called"] = True

        def rollback(self) -> None:
            session_state["rollback_called"] = True

        def refresh(self, report) -> None:
            pass

    def failing_save_report(session, report):
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr(report_module, "Session", FailingSession)
    monkeypatch.setattr(report_module, "save_report", failing_save_report)

    incident_id = uuid4()

    with pytest.raises(DatabaseAppError) as exc_info:
        ReportGenerationService._persist_report(
            incident_id=incident_id,
            model="fake/test-model",
            content=valid_report_content,
        )

    assert exc_info.value.message == "Could not persist report"
    assert exc_info.value.metadata["incident_id"] == str(incident_id)
    assert session_state["rollback_called"] is True
    assert session_state["commit_called"] is False
