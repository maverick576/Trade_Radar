"""Scheduler service for recurring cron jobs (Market Brief, backups, news refresh)."""

import asyncio

from arq.connections import RedisSettings

from traderadar.core.config import get_settings
from traderadar.core.logging import get_logger
from traderadar.services.runner import run_service

logger = get_logger("traderadar.scheduler")


class SchedulerSettings:
    """Settings class for arq cron scheduler execution."""

    @classmethod
    def get_redis_settings(cls) -> RedisSettings:
        settings = get_settings()
        return RedisSettings.from_dsn(settings.env.REDIS_URL)


async def scheduler_loop() -> None:
    """Scheduler background routine."""
    logger.info("scheduler_service_ready", note="Awaiting cron triggers (Brief, backup, recap)")
    while True:
        await asyncio.sleep(60)


def main() -> None:
    """CLI entrypoint."""
    run_service("scheduler", task_callback=scheduler_loop)


if __name__ == "__main__":
    main()
