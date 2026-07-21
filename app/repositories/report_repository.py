from uuid import UUID

from sqlmodel import Session, desc, select

from app.db.models.report import Report


def save_report(session: Session, report: Report) -> Report:
    session.add(report)
    return report


def find_report_by_id(session: Session, report_id: UUID) -> Report | None:
    return session.get(Report, report_id)


def find_reports_by_incident_id(
    session: Session,
    incident_id: UUID,
) -> list[Report]:
    statement = (
        select(Report)
        .where(Report.incident_id == incident_id)
        .order_by(desc(Report.created_at))
    )
    return list(session.exec(statement).all())
