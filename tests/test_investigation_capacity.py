import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vigilia.adapters.postgres.models import (
    Base,
    IncidentModel,
    InvestigationModel,
    OutboxEventModel,
)
from vigilia.adapters.postgres.unit_of_work import create_unit_of_work_factory
from vigilia.application.errors import RateLimitAppError
from vigilia.application.use_cases import RequestInvestigation
from vigilia.bootstrap.settings import Settings


@pytest.mark.skipif(
    os.getenv("VIGILIA_TEST_POSTGRES") != "true",
    reason="Set VIGILIA_TEST_POSTGRES=true to check admission against PostgreSQL",
)
def test_concurrent_admission_preserves_capacity_idempotency_and_outbox():
    async def scenario():
        settings = Settings()
        if settings.db_host == "localhost":
            settings.db_host = "127.0.0.1"
        schema = f"capacity_test_{uuid4().hex}"
        admin = create_async_engine(
            settings.database_url, connect_args={"connect_timeout": 5}
        )
        engine = create_async_engine(
            settings.database_url,
            connect_args={"connect_timeout": 5},
            execution_options={"schema_translate_map": {None: schema}},
        )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with admin.begin() as connection:
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            now = datetime.now(UTC)
            incident_ids = [uuid4() for _ in range(3)]
            async with sessions.begin() as session:
                session.add_all(
                    [
                        IncidentModel(
                            id=incident_id,
                            revision=1,
                            status="open",
                            service="capacity-test",
                            severity="warning",
                            title="Capacity test",
                            started_at=now,
                            updated_at=now,
                            created_at=now,
                        )
                        for incident_id in incident_ids
                    ]
                )
            request = RequestInvestigation(
                create_unit_of_work_factory(sessions),
                "simulated-v1",
                "investigations.requested.v1",
                max_active_investigations=2,
            )
            results = await asyncio.gather(
                *[
                    request.execute(incident_id, f"key-{incident_id}")
                    for incident_id in incident_ids
                ],
                return_exceptions=True,
            )
            successes = [
                result for result in results if not isinstance(result, Exception)
            ]
            rejections = [
                result for result in results if isinstance(result, RateLimitAppError)
            ]
            assert len(successes) == 2
            assert len(rejections) == 1
            assert rejections[0].code == "investigation_capacity_exceeded"
            async with sessions() as session:
                assert (
                    await session.scalar(select(func.count(InvestigationModel.id))) == 2
                )
                assert (
                    await session.scalar(select(func.count(OutboxEventModel.id))) == 2
                )
            existing = successes[0]
            reused = await request.execute(
                existing.incident_id, f"key-{existing.incident_id}"
            )
            assert reused.id == existing.id
            async with sessions.begin() as session:
                completed = await session.get(InvestigationModel, existing.id)
                completed.status = "completed"
                completed.completed_at = now
            rejected_incident = next(
                incident_id
                for incident_id, result in zip(incident_ids, results)
                if isinstance(result, RateLimitAppError)
            )
            accepted = await request.execute(
                rejected_incident, f"key-{rejected_incident}"
            )
            assert accepted.status == "queued"
            async with sessions() as session:
                active = await session.scalar(
                    select(func.count(InvestigationModel.id)).where(
                        InvestigationModel.status.in_(
                            ("queued", "running", "retry_wait")
                        )
                    )
                )
                assert active == 2
                assert (
                    await session.scalar(select(func.count(OutboxEventModel.id))) == 3
                )
        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(
                    text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                )
            await admin.dispose()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())
