import asyncio
import os
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis import Redis

from vigilia.adapters.http.dependencies import get_application
from vigilia.adapters.http.errors import register_exception_handlers
from vigilia.adapters.http.rate_limits import RateLimitMiddleware
from vigilia.adapters.http.routes import router
from vigilia.adapters.llm import analyzer as analyzer_module
from vigilia.adapters.llm.analyzer import LiteLLMIncidentAnalyzer
from vigilia.adapters.redis.controls import RedisCallLimiter, RedisTrafficControls
from vigilia.application.errors import NotFoundAppError, TransientInvestigationError
from vigilia.domain.models import IncidentSnapshot, InvestigationContext

REDIS_URL = os.getenv("VIGILIA_TEST_REDIS_URL")
pytestmark = pytest.mark.skipif(
    not REDIS_URL, reason="Set VIGILIA_TEST_REDIS_URL to run Redis integration checks"
)


@pytest.fixture
def namespace():
    name = f"rate-limit-test-{uuid4().hex}"
    yield name
    with Redis.from_url(REDIS_URL) as client:
        prefix = RedisTrafficControls(REDIS_URL, name).prefix
        keys = list(client.scan_iter(f"{prefix}:*"))
        if keys:
            client.delete(*keys)


@contextmanager
def limited_client(application, namespace, *, url=None):
    application.settings.rate_limit_enabled = True
    application.traffic_controls = RedisTrafficControls(url or REDIS_URL, namespace)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await application.traffic_controls.close()

    app = FastAPI(lifespan=lifespan)
    app.state.vigilia = application
    app.dependency_overrides[get_application] = lambda: application
    register_exception_handlers(app)
    app.add_middleware(RateLimitMiddleware)
    app.include_router(router)
    with TestClient(app) as client:
        yield client


def test_atomic_quota_shared_between_clients_and_expires(namespace):
    async def scenario():
        instances = [RedisTrafficControls(REDIS_URL, namespace) for _ in range(2)]
        try:
            decisions = await asyncio.gather(
                *[
                    instances[index % 2].check_rate(
                        "api", "secret-principal", 5, window_seconds=0.5
                    )
                    for index in range(24)
                ]
            )
            assert sum(decision.allowed for decision in decisions) == 5
            rejected = [decision for decision in decisions if not decision.allowed]
            assert all(decision.retry_after_seconds == 1 for decision in rejected)
            keys = await instances[0].client.keys(f"{instances[0].prefix}:*")
            assert all("secret-principal" not in key for key in keys)
            assert await instances[0].client.pttl(keys[0]) > 0
            await asyncio.sleep(0.55)
            assert (
                await instances[1].check_rate(
                    "api", "secret-principal", 5, window_seconds=0.5
                )
            ).allowed
        finally:
            for instance in instances:
                await instance.close()

    asyncio.run(scenario())


def test_authentication_precedes_principal_quota(
    application, configured_api_security, api_authorization_headers, namespace, caplog
):
    application.settings.rate_limit_api_per_minute = 2
    with limited_client(application, namespace) as client:
        assert client.get("/incidents").status_code == 401
        assert (
            client.get("/incidents", headers=api_authorization_headers).status_code
            == 200
        )
        response = client.get("/incidents", headers=api_authorization_headers)
        assert response.status_code == 200
        assert response.headers["X-RateLimit-Remaining"] == "0"
        rejected = client.get("/incidents", headers=api_authorization_headers)
        assert rejected.status_code == 429
        assert rejected.json()["error"]["code"] == "rate_limit_exceeded"
        assert 1 <= int(rejected.headers["Retry-After"]) <= 60
        assert rejected.headers["X-RateLimit-Limit"] == "2"
        assert "test-api-token" not in caplog.text
        assert client.get("/health").status_code == 200


def test_ingress_cannot_be_bypassed_with_forwarded_headers(application, namespace):
    application.settings.rate_limit_ingress_per_minute = 1
    with limited_client(application, namespace) as client:
        assert client.get("/incidents").status_code == 503
        rejected = client.get("/incidents", headers={"X-Forwarded-For": "192.0.2.9"})
        assert rejected.status_code == 429
        assert rejected.json()["error"]["metadata"]["bucket"] == "ingress"
        for _ in range(3):
            assert client.get("/health").status_code == 200


def test_expensive_endpoints_have_independent_quotas(
    application, configured_api_security, api_authorization_headers, namespace
):
    class MissingIncident:
        calls = 0

        async def execute(self, *args):
            self.calls += 1
            raise NotFoundAppError(message="Incident not found")

    application.request_investigation = MissingIncident()
    application.ingest_knowledge_document = None
    application.settings.rate_limit_investigations_per_minute = 2
    application.settings.rate_limit_knowledge_per_minute = 1
    with limited_client(application, namespace) as client:
        for _ in range(2):
            response = client.post(
                f"/incidents/{uuid4()}/investigations",
                headers=api_authorization_headers,
            )
            assert response.status_code == 404
        rejected = client.post(
            f"/incidents/{uuid4()}/investigations", headers=api_authorization_headers
        )
        assert rejected.status_code == 429
        assert application.request_investigation.calls == 2
        body = {
            "service": "payments",
            "source": "runbook",
            "title": "Runbook",
            "version": "1",
            "content": "Operational knowledge",
        }
        first = client.post(
            "/knowledge/documents", json=body, headers=api_authorization_headers
        )
        assert first.status_code == 503
        rejected = client.post(
            "/knowledge/documents", json=body, headers=api_authorization_headers
        )
        assert rejected.status_code == 429
        assert rejected.json()["error"]["metadata"]["bucket"] == "knowledge"


def test_webhook_quota_after_hmac_verification(
    application,
    configured_grafana_security,
    signed_grafana_request,
    grafana_payload,
    namespace,
):
    application.settings.rate_limit_webhooks_per_minute = 1
    body, headers = signed_grafana_request(grafana_payload)
    with limited_client(application, namespace) as client:
        bad_headers = {**headers, "X-Grafana-Alerting-Signature": "invalid"}
        assert (
            client.post(
                "/webhooks/grafana", content=body, headers=bad_headers
            ).status_code
            == 401
        )
        assert (
            client.post("/webhooks/grafana", content=body, headers=headers).status_code
            == 202
        )
        rejected = client.post("/webhooks/grafana", content=body, headers=headers)
        assert rejected.status_code == 429
        assert rejected.json()["error"]["metadata"]["bucket"] == "webhooks"


def test_backend_outage_returns_safe_503(
    application, configured_api_security, api_authorization_headers, namespace
):
    with limited_client(application, namespace, url="redis://127.0.0.1:1/0") as client:
        response = client.get("/incidents", headers=api_authorization_headers)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "rate_limit_backend_unavailable"
        assert response.headers["Retry-After"] == "5"
        assert "127.0.0.1" not in response.text
        assert client.get("/health").status_code == 200


def test_shared_slots_released_and_expired_tokens_cannot_remove_new_slots(namespace):
    async def scenario():
        controls = RedisTrafficControls(REDIS_URL, namespace)
        other = RedisTrafficControls(REDIS_URL, namespace)
        try:
            first = RedisCallLimiter(controls, "generation", 1, 1)
            second = RedisCallLimiter(other, "generation", 1, 5)
            stale = first.slot()
            await stale.__aenter__()
            with pytest.raises(TransientInvestigationError):
                async with second.slot():
                    pytest.fail("A second caller bypassed the shared limit")
            async with asyncio.timeout(5):
                while await controls.client.exists(
                    f"{controls.prefix}:slots:generation"
                ):
                    await asyncio.sleep(0.1)
            async with second.slot():
                await stale.__aexit__(None, None, None)
                with pytest.raises(TransientInvestigationError):
                    async with first.slot():
                        pytest.fail("An expired token removed a newer slot")
            async with first.slot():
                pass
        finally:
            await controls.close()
            await other.close()

    asyncio.run(scenario())


def test_provider_timeout_releases_capacity_without_external_calls(
    namespace, monkeypatch
):
    async def scenario():
        controls = RedisTrafficControls(REDIS_URL, namespace)
        limiter = controls.call_limiter("generation", 1, 0.05)

        async def stalled_provider(**kwargs):
            await asyncio.sleep(10)

        monkeypatch.setattr(analyzer_module.litellm, "acompletion", stalled_provider)
        analyzer = LiteLLMIncidentAnalyzer(
            model="test/model",
            api_key=None,
            api_base=None,
            timeout_seconds=0.05,
            max_output_tokens=1200,
            max_alerts=50,
            call_limiter=limiter,
        )
        now = datetime.now(UTC)
        context = InvestigationContext(
            IncidentSnapshot(
                id=uuid4(),
                revision=1,
                status="open",
                service="payments",
                severity="warning",
                title="Test incident",
                started_at=now,
                updated_at=now,
                resolved_at=None,
                alerts=(),
            )
        )
        try:
            with pytest.raises(TransientInvestigationError) as caught:
                await analyzer.analyze(context)
            assert caught.value.code == "analyzer_provider_unavailable"
            async with limiter.slot():
                pass
        finally:
            await controls.close()

    asyncio.run(scenario())
