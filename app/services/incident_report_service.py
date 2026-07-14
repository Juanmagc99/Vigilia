from uuid import UUID

from anyio import to_thread
from pydantic import ValidationError
from sqlmodel import Session

from app.core.errors import LLMProviderAppError
from app.db.session import engine
from app.schemas.incidents import IncidentDetail
from app.schemas.reports import IncidentReport
from app.services.incident_service import get_incident_detail
from app.services.llm_client import LLMClient
from app.services.prompt_renderer import PromptRenderer


class IncidentReportService:
    def __init__(
        self,
        *,
        prompt_renderer: PromptRenderer,
        llm_client: LLMClient,
    ) -> None:
        self._prompt_renderer = prompt_renderer
        self._llm_client = llm_client

    async def generate(self, *, incident_id: UUID) -> IncidentReport:
        incident = await to_thread.run_sync(
            self._load_incident_detail,
            incident_id,
        )

        prompt = self._prompt_renderer.render_incident_report(incident)
        raw_report = await self._llm_client.generate(prompt=prompt)

        try:
            return IncidentReport.model_validate_json(raw_report)
        except ValidationError as exc:
            raise LLMProviderAppError(
                message="LLM provider returned an invalid incident report",
                code="llm_invalid_report",
                metadata={
                    "operation": "validate_incident_report",
                    "incident_id": str(incident_id),
                },
            ) from exc

    @staticmethod
    def _load_incident_detail(incident_id: UUID) -> IncidentDetail:
        with Session(engine) as session:
            return get_incident_detail(
                session=session,
                incident_id=incident_id,
            )
