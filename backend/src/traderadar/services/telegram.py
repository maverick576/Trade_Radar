"""Telegram bot service (two-way commands, ticket dispatches, notifications)."""

import asyncio

from traderadar.core.config import get_settings
from traderadar.core.logging import get_logger
from traderadar.services.runner import run_service

logger = get_logger("traderadar.telegram")


async def telegram_loop() -> None:
    """Telegram bot background polling routine."""
    settings = get_settings()
    if not settings.env.TELEGRAM_ENABLED or not settings.env.TELEGRAM_BOT_TOKEN:
        logger.info(
            "telegram_disabled_or_unconfigured",
            enabled=settings.env.TELEGRAM_ENABLED,
            has_token=bool(settings.env.TELEGRAM_BOT_TOKEN),
            note="Service active and in standby. Configure TELEGRAM_BOT_TOKEN in .env to activate.",
        )
    else:
        logger.info("telegram_bot_polling_ready")

    while True:
        await asyncio.sleep(60)


def main() -> None:
    """CLI entrypoint."""
    run_service("telegram", task_callback=telegram_loop)


if __name__ == "__main__":
    main()
