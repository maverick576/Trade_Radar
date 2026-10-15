"""CLI healthcheck runner for Docker container health inspection."""

import asyncio
import os
import sys
import urllib.request
from datetime import UTC, datetime

import orjson
import redis.asyncio as aioredis


def check_http_health(url: str = "http://127.0.0.1:8000/api/health") -> int:
    """Check HTTP health endpoint."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TradeRadar-Healthcheck"})
        with urllib.request.urlopen(req, timeout=4) as response:
            if response.status == 200:
                return 0
            return 1
    except Exception:
        # Try fallback without /api prefix
        try:
            fallback = "http://127.0.0.1:8000/health"
            with urllib.request.urlopen(fallback, timeout=4) as response:
                return 0 if response.status == 200 else 1
        except Exception:
            return 1


async def check_service_heartbeat(service: str) -> int:
    """Check whether service heartbeat in Redis is fresh (< 45s)."""
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    try:
        client: aioredis.Redis = aioredis.from_url(redis_url, decode_responses=True)  # type: ignore[no-untyped-call]
        key = f"status:{service}"
        raw = await client.get(key)
        await client.close()

        if not raw:
            return 1

        data = orjson.loads(raw)
        ts_str = data.get("ts")
        if not ts_str:
            return 0  # Key exists, treat as alive

        heartbeat_time = datetime.fromisoformat(ts_str)
        if heartbeat_time.tzinfo is None:
            heartbeat_time = heartbeat_time.replace(tzinfo=UTC)

        age = (datetime.now(UTC) - heartbeat_time).total_seconds()
        return 0 if age <= 45 else 1
    except Exception:
        return 1


def main() -> None:
    """Entry point for CLI execution."""
    if len(sys.argv) < 2:
        sys.exit(check_http_health())

    target = sys.argv[1].lower()
    if target == "api":
        sys.exit(check_http_health())
    elif target == "service":
        if len(sys.argv) < 3:
            print("Missing service name argument", file=sys.stderr)
            sys.exit(1)
        service_name = sys.argv[2].lower()
        exit_code = asyncio.run(check_service_heartbeat(service_name))
        sys.exit(exit_code)
    else:
        print(f"Unknown healthcheck target: {target}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
