"""Health check endpoints for liveness and full system readiness inspection."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from traderadar.core.config import get_settings
from traderadar.core.db import ping_db
from traderadar.core.redis import get_all_heartbeats, ping_redis
from traderadar.core.time import to_iso_utc, utc_now

router = APIRouter(tags=["health"])

CORE_SERVICES = ["ingestor", "engine", "worker", "scheduler", "telegram"]


class HealthResponse(BaseModel):
    """Liveness probe response."""

    status: str
    version: str
    time: str


class InfrastructureHealth(BaseModel):
    """Status of supporting infrastructure."""

    database: str
    redis: str


class FullHealthResponse(BaseModel):
    """Comprehensive readiness probe response."""

    status: str
    version: str
    timestamp: str
    infrastructure: InfrastructureHealth
    services: dict[str, Any]
    ai_quota: dict[str, Any] | None = None


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Lightweight liveness probe for Docker and reverse proxy."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.env.APP_VERSION,
        time=to_iso_utc(utc_now()),
    )


@router.get("/health/full", response_model=FullHealthResponse)
async def get_full_health() -> FullHealthResponse:
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

    ai_quota = None
    if redis_ok:
        try:
            from traderadar.ai.ratelimit import AIRateLimiter
            from traderadar.core.redis import get_redis

            r_client = get_redis()
            limiter = AIRateLimiter(r_client, settings.env.AI_MAX_RPM, settings.env.AI_MAX_RPD)
            stats = await limiter.get_quota_stats()
            provider = settings.env.AI_PROVIDER
            if provider == "gemini" and not settings.env.GEMINI_API_KEY:
                provider = "template"
            elif provider == "claude" and not settings.env.ANTHROPIC_API_KEY:
                provider = "template"
            stats["provider"] = provider
            stats["model"] = (
                settings.env.GEMINI_MODEL
                if provider == "gemini"
                else (
                    settings.env.CLAUDE_MODEL if provider == "claude" else "template-rule-engine-v1"
                )
            )
            ai_quota = stats
        except Exception:
            pass

    return FullHealthResponse(
        status=overall_status,
        version=settings.env.APP_VERSION,
        timestamp=to_iso_utc(utc_now()),
        infrastructure=InfrastructureHealth(
            database="healthy" if db_ok else "unreachable",
            redis="healthy" if redis_ok else "unreachable",
        ),
        services=service_statuses,
        ai_quota=ai_quota,
    )
