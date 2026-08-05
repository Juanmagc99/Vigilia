from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.security import verify_api_token
from app.core.errors import InternalAppError
from app.db.session import DatabaseSession
from app.schemas.errors import ErrorResponse
from app.schemas.incidents import IncidentDetail, IncidentSummary
from app.schemas.reports import ReportRead
from app.services.incident_service import (
    get_incident_detail,
    list_incident_summaries,
)
from app.services.report_generation_service import ReportGenerationService
from app.services.report_service import list_reports_for_incident


router = APIRouter(
    prefix="/incidents",
    tags=["incidents"],
    dependencies=[Depends(verify_api_token)],
)


def get_report_generation_service(request: Request) -> ReportGenerationService:
    service = request.app.state.report_generation_service

    if service is None:
        raise InternalAppError(
            message="LLM incident reports are not configured",
            code="llm_not_configured",
            metadata={
                "required_settings": [
                    "VIGILIA_LLM_API_KEY",
                    "VIGILIA_LLM_MODEL",
                ],
            },
        )

    return service


ReportGenerationServiceDependency = Annotated[
    ReportGenerationService,
    Depends(get_report_generation_service),
]


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
    "/{incident_id}/reports",
    response_model=list[ReportRead],
    responses={
        500: {
            "model": ErrorResponse,
            "description": "Could not list reports for the incident",
        },
    },
)
def list_incident_reports(
    incident_id: UUID,
    session: DatabaseSession,
) -> list[ReportRead]:
    return list_reports_for_incident(
        session=session,
        incident_id=incident_id,
    )


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


@router.post(
    "/{incident_id}/report",
    response_model=ReportRead,
    responses={
        409: {
            "model": ErrorResponse,
            "description": "A report is already being generated for the incident",
        },
        404: {
            "model": ErrorResponse,
            "description": "Incident not found",
        },
        500: {
            "model": ErrorResponse,
            "description": "LLM incident reports are not configured",
        },
        502: {
            "model": ErrorResponse,
            "description": "LLM provider failed or returned an invalid report",
        },
        504: {
            "model": ErrorResponse,
            "description": "LLM provider timed out",
        },
    },
)
async def generate_incident_report(
    incident_id: UUID,
    report_generation_service: ReportGenerationServiceDependency,
) -> ReportRead:
    return await report_generation_service.generate(incident_id=incident_id)
