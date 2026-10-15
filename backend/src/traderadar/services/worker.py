"""Worker service for background jobs (AI comments, backtest, ML training)."""

import asyncio
from typing import Any

from arq.connections import RedisSettings

from traderadar.core.config import get_settings
from traderadar.core.logging import get_logger
from traderadar.services.runner import run_service

logger = get_logger("traderadar.worker")


async def ping_job(ctx: dict[str, Any]) -> str:
    """Sample health/test job for arq worker."""
    return "pong"


class WorkerSettings:
    """Settings class for arq worker execution."""

    functions = [ping_job]
    max_jobs = 2
    job_timeout = 300

    @classmethod
    def get_redis_settings(cls) -> RedisSettings:
        settings = get_settings()
        # Parse host and port from REDIS_URL if needed
        return RedisSettings.from_dsn(settings.env.REDIS_URL)


async def worker_loop() -> None:
    """Worker background routine."""
    logger.info("worker_service_ready", note="Awaiting AI & backtest background jobs")
    while True:
        await asyncio.sleep(60)


def main() -> None:
    """CLI entrypoint."""
    run_service("worker", task_callback=worker_loop)


if __name__ == "__main__":
    main()
