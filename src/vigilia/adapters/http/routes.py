from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy import text

from vigilia.adapters.grafana.normalizer import normalize_grafana_payload
from vigilia.adapters.grafana.schemas import GrafanaWebhookPayload
from vigilia.adapters.http.dependencies import ApplicationDependency
from vigilia.adapters.http.security import verify_api_token, verify_grafana_signature
from vigilia.application.contracts import (
    IncidentDetail,
    IncidentSummary,
    InvestigationRead,
    LegacyReportRead,
)


router = APIRouter()


@router.get("/health", tags=["health"])
async def health(application: ApplicationDependency) -> dict[str, str]:
    return {
        "status": "ok",
        "service": application.settings.app_name,
        "env": application.settings.environment,
    }


@router.get("/ready", tags=["health"])
async def ready(application: ApplicationDependency) -> dict[str, str]:
    async with application.sessions() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ready"}


@router.post(
    "/webhooks/grafana",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["grafana"],
    dependencies=[Depends(verify_grafana_signature)],
)
async def receive_grafana_webhook(
    payload: GrafanaWebhookPayload, application: ApplicationDependency
) -> dict[str, object]:
    normalized = normalize_grafana_payload(payload)
    result = await application.ingest_alerts.execute(normalized, len(payload.alerts))
    return {
        "status": "accepted",
        "source": "grafana",
        **result.model_dump(),
        "group_key": payload.groupKey,
    }


protected = APIRouter(dependencies=[Depends(verify_api_token)])


@protected.get("/incidents", response_model=list[IncidentSummary], tags=["incidents"])
async def list_incidents(application: ApplicationDependency) -> list[IncidentSummary]:
    return await application.incident_queries.list()


@protected.get(
    "/incidents/{incident_id}", response_model=IncidentDetail, tags=["incidents"]
)
async def get_incident(
    incident_id: UUID, application: ApplicationDependency
) -> IncidentDetail:
    return await application.incident_queries.get(incident_id)


@protected.post(
    "/incidents/{incident_id}/investigations",
    response_model=InvestigationRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["investigations"],
)
async def request_investigation(
    incident_id: UUID,
    response: Response,
    application: ApplicationDependency,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ] = None,
) -> InvestigationRead:
    investigation = await application.request_investigation.execute(
        incident_id, idempotency_key
    )
    response.headers["Location"] = f"/investigations/{investigation.id}"
    return investigation


@protected.get(
    "/investigations/{investigation_id}",
    response_model=InvestigationRead,
    tags=["investigations"],
)
async def get_investigation(
    investigation_id: UUID, application: ApplicationDependency
) -> InvestigationRead:
    return await application.investigation_queries.get(investigation_id)


@protected.get(
    "/incidents/{incident_id}/investigations",
    response_model=list[InvestigationRead],
    tags=["investigations"],
)
async def list_investigations(
    incident_id: UUID, application: ApplicationDependency
) -> list[InvestigationRead]:
    return await application.investigation_queries.list_for_incident(incident_id)


@protected.get(
    "/incidents/{incident_id}/reports",
    response_model=list[LegacyReportRead],
    tags=["legacy"],
    deprecated=True,
)
async def list_legacy_reports(
    incident_id: UUID, response: Response, application: ApplicationDependency
) -> list[LegacyReportRead]:
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "undetermined"
    return await application.investigation_queries.list_legacy_reports(incident_id)


router.include_router(protected)
