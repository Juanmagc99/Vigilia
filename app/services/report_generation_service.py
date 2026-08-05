from uuid import UUID

from anyio import CapacityLimiter, Lock, to_thread
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.core.errors import ConflictAppError, DatabaseAppError, LLMProviderAppError
from app.db.models.report import Report
from app.db.session import engine
from app.repositories.report_repository import save_report
from app.schemas.incidents import IncidentDetail
from app.schemas.reports import ReportContent, ReportRead
from app.services.incident_service import get_incident_detail
from app.services.llm_client import LLMClient
from app.services.prompt_renderer import PromptRenderer


class ReportGenerationService:
    def __init__(
        self,
        *,
        prompt_renderer: PromptRenderer,
        llm_client: LLMClient,
        llm_limiter: CapacityLimiter,
    ) -> None:
        self._prompt_renderer = prompt_renderer
        self._llm_client = llm_client
        self._llm_limiter = llm_limiter
        self._in_progress_incident_ids: set[UUID] = set()
        self._in_progress_lock = Lock()

    async def generate(self, *, incident_id: UUID) -> ReportRead:
        generation_acquired = False
        try:
            await self._acquire_incident_generation(incident_id)
            generation_acquired = True

            incident = await to_thread.run_sync(
                self._load_incident_detail,
                incident_id,
            )

            prompt = self._prompt_renderer.render_incident_report(incident)

            async with self._llm_limiter:
                raw_report = await self._llm_client.generate(prompt=prompt)

            try:
                content = ReportContent.model_validate_json(raw_report)
            except ValidationError as exc:
                raise LLMProviderAppError(
                    message="LLM provider returned an invalid report",
                    code="llm_invalid_report",
                    metadata={
                        "operation": "validate_report_content",
                        "incident_id": str(incident_id),
                    },
                ) from exc

            return await to_thread.run_sync(
                self._persist_report,
                incident_id,
                self._llm_client.model,
                content,
            )
        finally:
            if generation_acquired:
                await self._release_incident_generation(incident_id)

    async def _acquire_incident_generation(self, incident_id: UUID) -> None:
        async with self._in_progress_lock:
            if incident_id in self._in_progress_incident_ids:
                raise ConflictAppError(
                    message="A report is already being generated for this incident",
                    code="report_generation_in_progress",
                    metadata={
                        "incident_id": str(incident_id),
                        "operation": "generate_report",
                    },
                )

            self._in_progress_incident_ids.add(incident_id)

    async def _release_incident_generation(self, incident_id: UUID) -> None:
        async with self._in_progress_lock:
            self._in_progress_incident_ids.discard(incident_id)

    @staticmethod
    def _load_incident_detail(incident_id: UUID) -> IncidentDetail:
        with Session(engine) as session:
            return get_incident_detail(
                session=session,
                incident_id=incident_id,
            )

    @staticmethod
    def _persist_report(
        incident_id: UUID,
        model: str,
        content: ReportContent,
    ) -> ReportRead:
        with Session(engine) as session:
            try:
                report = Report(
                    incident_id=incident_id,
                    model=model,
                    content=content.model_dump(mode="json"),
                )

                save_report(session, report)
                session.commit()
                session.refresh(report)

                return ReportRead.model_validate(report)
            except SQLAlchemyError as exc:
                session.rollback()
                raise DatabaseAppError(
                    message="Could not persist report",
                    metadata={
                        "operation": "persist_report",
                        "entity": "report",
                        "incident_id": str(incident_id),
                    },
                ) from exc
