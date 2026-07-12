from uuid import UUID

from fastapi import APIRouter

from app.db.session import DatabaseSession
from app.schemas.errors import ErrorResponse
from app.schemas.incidents import IncidentDetail, IncidentSummary
from app.services.incident_service import (
    get_incident_detail,
    list_incident_summaries,
)


router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get(
    "",
    response_model=list[IncidentSummary],
    responses={
        500: {
            "model": ErrorResponse,
            "description": "Could not list incidents",
        },
    },
)
def list_incidents(
    session: DatabaseSession,
) -> list[IncidentSummary]:
    return list_incident_summaries(session)


@router.get(
    "/{incident_id}",
    response_model=IncidentDetail,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Incident not found",
        },
        500: {
            "model": ErrorResponse,
            "description": "Could not get incident detail",
        },
    },
)
def get_incident(
    incident_id: UUID,
    session: DatabaseSession,
) -> IncidentDetail:
    return get_incident_detail(
        session=session,
        incident_id=incident_id,
    )
