"""Telegram bot application lifecycle and handler registration.

Manages python-telegram-bot Application instance, command routing,
and long polling execution loop.
"""

from typing import Any, cast

from telegram import Bot
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from traderadar.core.config import Settings, get_settings
from traderadar.core.logging import get_logger
from traderadar.telegram.handlers import (
    analisa_command,
    brief_command,
    callback_query_handler,
    eksekusi_command,
    help_command,
    kalender_command,
    kalibrasi_command,
    pause_command,
    posisi_command,
    reply_message_handler,
    resume_command,
    start_command,
    ticket_command,
    tutup_command,
    winrate_command,
)

logger = get_logger("traderadar.telegram.bot")


class TradeRadarBot:
    """Wraps python-telegram-bot Application with TradeRadar commands."""

    def __init__(self, token: str, settings: Settings | None = None) -> None:
        self.token = token
        self.settings = settings or get_settings()
        self.application: Any = Application.builder().token(token).build()
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register all two-way commands, callback queries, and reply text handlers."""
        app = self.application

        # 1. Standard Commands
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("brief", brief_command))
        app.add_handler(CommandHandler("analisa", analisa_command))
        app.add_handler(CommandHandler("ticket", ticket_command))
        app.add_handler(CommandHandler("kalibrasi", kalibrasi_command))
        app.add_handler(CommandHandler("eksekusi", eksekusi_command))
        app.add_handler(CommandHandler("tutup", tutup_command))
        app.add_handler(CommandHandler("posisi", posisi_command))
        app.add_handler(CommandHandler("winrate", winrate_command))
        app.add_handler(CommandHandler("kalender", kalender_command))
        app.add_handler(CommandHandler("pause", pause_command))
        app.add_handler(CommandHandler("resume", resume_command))

        # 2. Interactive Callback Queries (inline button actions)
        app.add_handler(CallbackQueryHandler(callback_query_handler))

        # 3. Text Message Handler (e.g. fill price replies)
        app.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), reply_message_handler)
        )

        logger.info("telegram_bot_handlers_registered")

    @property
    def bot(self) -> Bot:
        """Access underlying Telegram Bot instance."""
        return cast(Bot, self.application.bot)

    async def start(self) -> None:
        """Initialize and start Telegram application updater with long polling."""
        logger.info("starting_telegram_bot_long_polling")
        await self.application.initialize()
        await self.application.start()
        if self.application.updater:
            await self.application.updater.start_polling(drop_pending_updates=True)

    async def stop(self) -> None:
        """Gracefully stop updater and shutdown application."""
        logger.info("stopping_telegram_bot")
        if self.application.updater and self.application.updater.running:
            await self.application.updater.stop()
        if self.application.running:
            await self.application.stop()
        await self.application.shutdown()


def create_bot(settings: Settings | None = None) -> TradeRadarBot | None:
    """Factory creating TradeRadarBot if enabled and configured."""
    cfg = settings or get_settings()
    if not cfg.env.TELEGRAM_ENABLED:
        logger.info("telegram_service_disabled_by_env")
        return None

    token = cfg.env.TELEGRAM_BOT_TOKEN.strip()
    if not token:
        logger.info("telegram_bot_token_empty_standby")
        return None

    return TradeRadarBot(token=token, settings=cfg)
