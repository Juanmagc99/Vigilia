import math
from contextlib import asynccontextmanager
from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4

from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError

from vigilia.application.errors import (
    RateLimitBackendUnavailableAppError,
    TransientInvestigationError,
)
from vigilia.observability.logging import get_logger

logger = get_logger(__name__)

RATE_LIMIT_SCRIPT = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
local count = redis.call('ZCARD', KEYS[1])
if count >= limit then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    local reset = tonumber(oldest[2]) + window
    return {0, 0, reset - now, reset}
end
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('PEXPIRE', KEYS[1], window)
local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
return {1, limit - count - 1, 0, tonumber(oldest[2]) + window}
"""

ACQUIRE_SLOT_SCRIPT = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    return {0, tonumber(oldest[2]) - now}
end
redis.call('ZADD', KEYS[1], now + tonumber(ARGV[2]), ARGV[3])
local latest = redis.call('ZRANGE', KEYS[1], -1, -1, 'WITHSCORES')
redis.call('PEXPIRE', KEYS[1], tonumber(latest[2]) - now)
return {1, 0}
"""


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int
    reset_at: int

    @property
    def headers(self) -> dict[str, str]:
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_at),
        }


class RedisTrafficControls:
    def __init__(self, url: str, namespace: str) -> None:
        self.client = Redis.from_url(
            url,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True,
            retry=Retry(NoBackoff(), 0),
        )
        self.prefix = f"vigilia:{sha256(namespace.encode()).hexdigest()[:16]}"

    async def close(self) -> None:
        await self.client.aclose()

    async def ready(self) -> None:
        try:
            await self.client.ping()
        except (RedisError, OSError) as exc:
            raise RateLimitBackendUnavailableAppError() from exc

    async def check_rate(
        self, bucket: str, subject: str, limit: int, *, window_seconds: float = 60
    ) -> RateLimitDecision:
        key = f"{self.prefix}:rate:{bucket}:{sha256(subject.encode()).hexdigest()}"
        try:
            allowed, remaining, retry_ms, reset_ms = await self.client.eval(
                RATE_LIMIT_SCRIPT,
                1,
                key,
                math.ceil(window_seconds * 1000),
                limit,
                uuid4().hex,
            )
        except (RedisError, OSError) as exc:
            raise RateLimitBackendUnavailableAppError() from exc
        return RateLimitDecision(
            allowed=bool(allowed),
            limit=limit,
            remaining=int(remaining),
            retry_after_seconds=max(1, math.ceil(int(retry_ms) / 1000)),
            reset_at=math.ceil(int(reset_ms) / 1000),
        )

    def call_limiter(
        self, pool: str, limit: int, timeout_seconds: float
    ) -> "RedisCallLimiter":
        return RedisCallLimiter(self, pool, limit, math.ceil(timeout_seconds) + 10)


@dataclass(frozen=True)
class RedisCallLimiter:
    controls: RedisTrafficControls
    pool: str
    limit: int
    lease_seconds: int

    @asynccontextmanager
    async def slot(self):
        key = f"{self.controls.prefix}:slots:{self.pool}"
        token = uuid4().hex
        try:
            allowed, retry_ms = await self.controls.client.eval(
                ACQUIRE_SLOT_SCRIPT,
                1,
                key,
                self.limit,
                self.lease_seconds * 1000,
                token,
            )
        except (RedisError, OSError) as exc:
            raise TransientInvestigationError(
                message="Provider call limits are temporarily unavailable",
                code="provider_call_limits_unavailable",
                retry_after_seconds=5,
            ) from exc
        if not allowed:
            raise TransientInvestigationError(
                message="The provider call concurrency limit has been reached",
                code="provider_call_capacity_exceeded",
                metadata={"pool": self.pool, "limit": self.limit},
                retry_after_seconds=max(1, math.ceil(int(retry_ms) / 1000)),
            )
        try:
            yield
        finally:
            try:
                await self.controls.client.zrem(key, token)
            except (RedisError, OSError):
                logger.warning("Provider call slot release failed pool=%s", self.pool)
