"""Redis connection pool, Pub/Sub, and health/heartbeat utilities."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import orjson
import redis.asyncio as aioredis

from traderadar.core.config import get_settings

_redis_pool: aioredis.ConnectionPool | None = None
_redis_client: aioredis.Redis | None = None


def get_redis_pool() -> aioredis.ConnectionPool:
    """Get or create singleton Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = aioredis.ConnectionPool.from_url(
            settings.env.REDIS_URL,
            max_connections=20,
            decode_responses=True,
        )
    return _redis_pool


def get_redis() -> aioredis.Redis:
    """Get or create singleton Redis client."""
    global _redis_client
    if _redis_client is None:
        pool = get_redis_pool()
        _redis_client = aioredis.Redis(connection_pool=pool)
    return _redis_client


@asynccontextmanager
async def get_redis_context() -> AsyncGenerator[aioredis.Redis, None]:
    """Context manager for obtaining Redis client."""
    client = get_redis()
    yield client


async def ping_redis() -> bool:
    """Check Redis connectivity."""
    try:
        client = get_redis()
        return bool(await client.ping())
    except Exception:
        return False


async def set_heartbeat(service: str, payload: dict[str, Any], ttl_seconds: int = 30) -> None:
    """Register or update service heartbeat with TTL."""
    client = get_redis()
    key = f"status:{service}"
    raw = orjson.dumps(payload).decode("utf-8")
    await client.set(key, raw, ex=ttl_seconds)


async def get_heartbeat(service: str) -> dict[str, Any] | None:
    """Retrieve service heartbeat if still alive within TTL."""
    client = get_redis()
    key = f"status:{service}"
    raw = await client.get(key)
    if not raw:
        return None
    try:
        return orjson.loads(raw)  # type: ignore[no-any-return]
    except Exception:
        return None


async def get_all_heartbeats(services: list[str]) -> dict[str, dict[str, Any] | None]:
    """Fetch status for all listed services."""
    results: dict[str, dict[str, Any] | None] = {}
    for svc in services:
        results[svc] = await get_heartbeat(svc)
    return results


async def close_redis() -> None:
    """Close Redis client and connection pool."""
    global _redis_client, _redis_pool
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None
