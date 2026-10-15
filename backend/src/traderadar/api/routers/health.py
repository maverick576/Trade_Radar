"""Health check endpoints for liveness and full system readiness inspection."""

from typing import Any

from fastapi import APIRouter

from traderadar.core.config import get_settings
from traderadar.core.db import ping_db
from traderadar.core.redis import get_all_heartbeats, ping_redis
from traderadar.core.time import to_iso_utc, utc_now

router = APIRouter(tags=["health"])

CORE_SERVICES = ["ingestor", "engine", "worker", "scheduler", "telegram"]


@router.get("/health")
async def get_health() -> dict[str, Any]:
    """Lightweight liveness probe for Docker and reverse proxy."""
    settings = get_settings()
    return {
        "status": "ok",
        "version": settings.env.APP_VERSION,
        "time": to_iso_utc(utc_now()),
    }


@router.get("/health/full")
async def get_full_health() -> dict[str, Any]:
    """Comprehensive readiness probe checking DB, Redis, and internal service heartbeats."""
    settings = get_settings()

    db_ok = await ping_db()
    redis_ok = await ping_redis()

    service_statuses = await get_all_heartbeats(CORE_SERVICES)

    # API itself is healthy if responding
    service_statuses["api"] = {
        "service": "api",
        "status": "healthy",
        "version": settings.env.APP_VERSION,
        "ts": to_iso_utc(utc_now()),
    }

    # Evaluate overall system health
    infra_ok = db_ok and redis_ok
    overall_status = "healthy" if infra_ok else "degraded"

    return {
        "status": overall_status,
        "version": settings.env.APP_VERSION,
        "timestamp": to_iso_utc(utc_now()),
        "infrastructure": {
            "database": "healthy" if db_ok else "unreachable",
            "redis": "healthy" if redis_ok else "unreachable",
        },
        "services": service_statuses,
    }
