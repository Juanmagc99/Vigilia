from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from vigilia.adapters.llm.analyzer import LiteLLMIncidentAnalyzer
from vigilia.adapters.postgres.session import create_engine, create_session_factory
from vigilia.adapters.postgres.unit_of_work import create_unit_of_work_factory
from vigilia.adapters.simulation.analyzer import SimulatedIncidentAnalyzer
from vigilia.application.ports import IncidentAnalyzer
from vigilia.application.use_cases import (
    CorrelateAlert,
    ExecuteInvestigation,
    IncidentQueries,
    IngestAlerts,
    InvestigationQueries,
    RequestInvestigation,
)
from vigilia.bootstrap.settings import Settings


@dataclass(frozen=True)
class ProcessResources:
    settings: Settings
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]


@dataclass(frozen=True)
class ApiApplication(ProcessResources):
    ingest_alerts: IngestAlerts
    request_investigation: RequestInvestigation
    incident_queries: IncidentQueries
    investigation_queries: InvestigationQueries


@dataclass(frozen=True)
class WorkerApplication(ProcessResources):
    correlate_alert: CorrelateAlert
    execute_investigation: ExecuteInvestigation


def _database_resources(settings: Settings):
    engine = create_engine(settings.database_url)
    sessions = create_session_factory(engine)
    return engine, sessions, create_unit_of_work_factory(sessions)


def compose_api(settings: Settings) -> ApiApplication:
    engine, sessions, unit_of_work = _database_resources(settings)
    return ApiApplication(
        settings=settings,
        engine=engine,
        sessions=sessions,
        ingest_alerts=IngestAlerts(unit_of_work, settings.alerts_received_topic),
        request_investigation=RequestInvestigation(
            unit_of_work,
            settings.analyzer_version,
            settings.investigations_requested_topic,
        ),
        incident_queries=IncidentQueries(unit_of_work),
        investigation_queries=InvestigationQueries(unit_of_work),
    )


def compose_worker(settings: Settings) -> WorkerApplication:
    engine, sessions, unit_of_work = _database_resources(settings)
    analyzer = _compose_analyzer(settings)
    return WorkerApplication(
        settings=settings,
        engine=engine,
        sessions=sessions,
        correlate_alert=CorrelateAlert(
            unit_of_work, settings.incident_correlation_window_minutes
        ),
        execute_investigation=ExecuteInvestigation(
            unit_of_work,
            analyzer,
            settings.investigations_requested_topic,
            settings.investigation_lease_seconds,
            settings.investigation_max_attempts,
            settings.investigation_retry_max_delay_seconds,
        ),
    )


def _compose_analyzer(settings: Settings) -> IncidentAnalyzer:
    if settings.investigation_analyzer == "simulated":
        return SimulatedIncidentAnalyzer()
    return LiteLLMIncidentAnalyzer(
        model=settings.llm_model or "",
        api_key=(
            settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
        ),
        api_base=settings.llm_api_base,
        timeout_seconds=settings.llm_timeout_seconds,
        max_output_tokens=settings.llm_max_output_tokens,
        max_alerts=settings.llm_max_alerts,
    )


def compose_publisher(settings: Settings) -> ProcessResources:
    engine, sessions, _ = _database_resources(settings)
    return ProcessResources(settings=settings, engine=engine, sessions=sessions)
