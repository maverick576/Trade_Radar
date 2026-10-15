"""Redis-backed rate limiting and quota tracking for AI providers."""

from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis


class AIRateLimiter:
    """Token/counter rate limiter for AI requests in Redis."""

    def __init__(
        self, redis_client: aioredis.Redis, rpm_limit: int = 5, rpd_limit: int = 100
    ) -> None:
        self.redis = redis_client
        self.rpm_limit = rpm_limit
        self.rpd_limit = rpd_limit

    def _get_minute_key(self, dt: datetime) -> str:
        return f"ratelimit:ai:rpm:{dt.strftime('%Y%m%d%H%M')}"

    def _get_day_key(self, dt: datetime) -> str:
        return f"ratelimit:ai:rpd:{dt.strftime('%Y%m%d')}"

    async def get_quota_stats(self) -> dict[str, Any]:
        """Get current usage and remaining quota for RPM and RPD."""
        now = datetime.now(UTC)
        min_key = self._get_minute_key(now)
        day_key = self._get_day_key(now)

        pipe = self.redis.pipeline()
        pipe.get(min_key)
        pipe.get(day_key)
        results = await pipe.execute()

        rpm_used = int(results[0]) if results[0] else 0
        rpd_used = int(results[1]) if results[1] else 0

        return {
            "rpm_used": rpm_used,
            "rpm_limit": self.rpm_limit,
            "rpm_remaining": max(0, self.rpm_limit - rpm_used),
            "rpd_used": rpd_used,
            "rpd_limit": self.rpd_limit,
            "rpd_remaining": max(0, self.rpd_limit - rpd_used),
        }

    async def check_and_consume(self) -> tuple[bool, str | None, dict[str, Any]]:
        """Check if request is within limits and increment counters atomically.

        Returns:
            (allowed, rejection_reason, quota_stats)
        """
        now = datetime.now(UTC)
        min_key = self._get_minute_key(now)
        day_key = self._get_day_key(now)

        stats = await self.get_quota_stats()

        if stats["rpm_used"] >= self.rpm_limit:
            return False, f"Batas laju per menit (RPM: {self.rpm_limit}) tercapai.", stats

        if stats["rpd_used"] >= self.rpd_limit:
            return False, f"Batas kuota harian (RPD: {self.rpd_limit}) tercapai.", stats

        # Increment atomically
        pipe = self.redis.pipeline()
        pipe.incr(min_key)
        pipe.expire(min_key, 120)
        pipe.incr(day_key)
        pipe.expire(day_key, 172800)
        await pipe.execute()

        # Update returned stats
        stats["rpm_used"] += 1
        stats["rpm_remaining"] = max(0, self.rpm_limit - stats["rpm_used"])
        stats["rpd_used"] += 1
        stats["rpd_remaining"] = max(0, self.rpd_limit - stats["rpd_used"])

        return True, None, stats
