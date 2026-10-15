"""Telegram bot service entrypoint (two-way polling, ticket dispatches, notifications)."""

import asyncio

from traderadar.core.config import get_settings
from traderadar.core.logging import get_logger
from traderadar.services.runner import run_service
from traderadar.telegram.bot import create_bot
from traderadar.telegram.notifier import (
    TelegramNotifier,
    run_signals_consumer,
    run_ui_events_consumer,
)

logger = get_logger("traderadar.telegram")


async def telegram_loop() -> None:
    """Telegram bot background polling and notification consumer routine."""
    settings = get_settings()

    if not settings.env.TELEGRAM_ENABLED or not settings.env.TELEGRAM_BOT_TOKEN:
        logger.info(
            "telegram_disabled_or_unconfigured",
            enabled=settings.env.TELEGRAM_ENABLED,
            has_token=bool(settings.env.TELEGRAM_BOT_TOKEN),
            note=(
                "Service aktif dalam mode standby. Isi TELEGRAM_BOT_TOKEN dan "
                "TELEGRAM_ALLOWED_CHAT_IDS di .env untuk mengaktifkan bot."
            ),
        )
        while True:
            await asyncio.sleep(60)

    bot_app = create_bot(settings)
    if not bot_app:
        logger.warning("failed_to_initialize_telegram_bot")
        while True:
            await asyncio.sleep(60)

    notifier = TelegramNotifier(bot=bot_app.bot, settings=settings)

    try:
        # Start bot long polling
        await bot_app.start()
        logger.info("telegram_bot_service_online")

        # Concurrently consume Redis signals stream and UI events
        await asyncio.gather(
            run_signals_consumer(notifier),
            run_ui_events_consumer(notifier),
        )
    except asyncio.CancelledError:
        logger.info("telegram_service_cancelling")
    finally:
        await bot_app.stop()
        logger.info("telegram_service_stopped_cleanly")


def main() -> None:
    """CLI entrypoint."""
    run_service("telegram", task_callback=telegram_loop)


if __name__ == "__main__":
    main()
