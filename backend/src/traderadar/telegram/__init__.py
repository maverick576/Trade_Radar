"""TradeRadar Telegram bot package (two-way commands, chart rendering, notifications)."""

from traderadar.telegram.bot import TradeRadarBot, create_bot
from traderadar.telegram.charts import load_candles_and_render_chart, render_candlestick_chart
from traderadar.telegram.notifier import (
    TelegramNotifier,
    run_signals_consumer,
    run_ui_events_consumer,
)
from traderadar.telegram.whitelist import (
    get_active_notification_chats,
    get_allowed_chat_ids,
    is_chat_allowed,
    whitelist_only,
)

__all__ = [
    "TradeRadarBot",
    "create_bot",
    "render_candlestick_chart",
    "load_candles_and_render_chart",
    "TelegramNotifier",
    "run_signals_consumer",
    "run_ui_events_consumer",
    "get_allowed_chat_ids",
    "is_chat_allowed",
    "get_active_notification_chats",
    "whitelist_only",
]
