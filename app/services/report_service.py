from uuid import UUID

from sqlmodel import Session

from app.core.errors import NotFoundAppError
from app.repositories.report_repository import find_report_by_id, find_reports_by_incident_id
from app.schemas.reports import ReportRead


def get_report(
    session: Session,
    report_id: UUID,
) -> ReportRead:
    report = find_report_by_id(
        session=session,
        report_id=report_id,
    )

    if report is None:
        raise NotFoundAppError(
            message="Report not found",
            metadata={"report_id": str(report_id)},
        )

    return ReportRead.model_validate(report)

def list_reports_by_incident(
    session: Session,
    incident_id: UUID
) -> list[ReportRead]:
    reports = find_reports_by_incident_id(
        session=session,
        incident_id=incident_id
    )

    return [
        ReportRead.model_validate(report)
        for report in reports
    ]