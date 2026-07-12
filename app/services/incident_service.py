from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.core.errors import DatabaseAppError, NotFoundAppError
from app.db.models.alert import Alert
from app.db.models.incident import Incident
from app.repositories.incident_repository import (
    find_alerts_by_incident,
    find_incident_by_id,
    find_incidents,
)
from app.schemas.alerts import AlertRead
from app.schemas.incidents import IncidentDetail, IncidentSummary


def list_incident_summaries(session: Session) -> list[IncidentSummary]:
    try:
        incidents = find_incidents(session)

        return [
            _incident_to_summary(incident)
            for incident in incidents
        ]
    except SQLAlchemyError as exc:
        session.rollback()
        raise DatabaseAppError(
            message="Could not list incidents",
            metadata={
                "operation": "list_incident_summaries",
                "entity": "incident",
            },
        ) from exc


def get_incident_detail(
    session: Session,
    incident_id: UUID,
) -> IncidentDetail:
    try:
        incident = find_incident_by_id(
            session=session,
            incident_id=incident_id,
        )

        if incident is None:
            raise NotFoundAppError(
                message="Incident not found",
                metadata={
                    "operation": "get_incident_detail",
                    "incident_id": str(incident_id),
                },
            )

        alerts = find_alerts_by_incident(
            session=session,
            incident_id=incident_id,
        )

        incident_summary = _incident_to_summary(incident)

        return IncidentDetail(
            **incident_summary.model_dump(),
            alerts=[
                _alert_to_read(alert)
                for alert in alerts
            ],
        )
    except NotFoundAppError:
        raise
    except SQLAlchemyError as exc:
        session.rollback()
        raise DatabaseAppError(
            message="Could not get incident detail",
            metadata={
                "operation": "get_incident_detail",
                "entity": "incident",
                "incident_id": str(incident_id),
            },
        ) from exc


def _incident_to_summary(incident: Incident) -> IncidentSummary:
    return IncidentSummary.model_validate(incident)


def _alert_to_read(alert: Alert) -> AlertRead:
    return AlertRead.model_validate(alert)


