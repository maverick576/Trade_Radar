"""Background event consumer and notification dispatcher for Telegram.

Consumes Redis Stream `signals` (consumer group `telegram`) and Pub/Sub `ui.events`
to broadcast Trade Tickets (with chart PNG, AI comments & inline buttons),
Paper trading exits (TP1/TP2/SL/time stop), ticket expirations, Market Briefs,
and 22:00 WIB daily recaps.
"""

import asyncio
import json
from datetime import UTC
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from traderadar.core.config import Settings, get_settings
from traderadar.core.db import get_db_session
from traderadar.core.events import (
    CHANNEL_UI_EVENTS,
    STREAM_SIGNALS,
    SignalEvent,
)
from traderadar.core.logging import get_logger
from traderadar.core.models import (
    AICommentRecord,
    PaperTradeRecord,
    RealExecutionRecord,
)
from traderadar.core.redis import get_redis_client
from traderadar.core.time import utc_now
from traderadar.services.ticket_store import get_latest_broker_calibration, get_ticket_by_id
from traderadar.telegram.charts import load_candles_and_render_chart
from traderadar.telegram.formatters import (
    format_brief_message,
    format_daily_recap_message,
    format_paper_exit_notification,
    format_system_status_notification,
    format_ticket_expired_notification,
    format_ticket_message,
)
from traderadar.telegram.whitelist import get_active_notification_chats

logger = get_logger("traderadar.telegram.notifier")
WIB = ZoneInfo("Asia/Jakarta")


class TelegramNotifier:
    """Dispatches proactive notifications to authorized Telegram subscribers."""

    def __init__(self, bot: Bot, settings: Settings | None = None) -> None:
        self.bot = bot
        self.settings = settings or get_settings()

    async def broadcast_message(
        self,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> int:
        """Send a Markdown message to all active, unpaused chats."""
        async with get_db_session() as session:
            chats = await get_active_notification_chats(session, self.settings)

        sent_count = 0
        for chat_id in chats:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN,
                )
                sent_count += 1
            except Exception as exc:
                logger.error("failed_to_send_telegram_message", chat_id=chat_id, error=str(exc))
        return sent_count

    async def broadcast_photo(
        self,
        photo_bytes: bytes,
        caption: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> int:
        """Send a photo with caption to all active, unpaused chats."""
        async with get_db_session() as session:
            chats = await get_active_notification_chats(session, self.settings)

        sent_count = 0
        for chat_id in chats:
            try:
                await self.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_bytes,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN,
                )
                sent_count += 1
            except Exception as exc:
                logger.error("failed_to_send_telegram_photo", chat_id=chat_id, error=str(exc))
        return sent_count

    async def notify_ticket(self, ticket_id: int) -> None:
        """Dispatch a newly created Trade Ticket with chart PNG, AI comment, and inline buttons."""
        wait_seconds = self.settings.app.telegram.wait_ai_seconds or 20
        start_time = asyncio.get_event_loop().time()

        async with get_db_session() as session:
            ticket = await get_ticket_by_id(session, ticket_id)
            if not ticket:
                logger.warning("ticket_not_found_for_notification", ticket_id=ticket_id)
                return

            # Wait for AI commentary if pending (up to wait_seconds)
            ai_comment_text: str | None = None
            while (asyncio.get_event_loop().time() - start_time) < wait_seconds:
                stmt_ai = (
                    select(AICommentRecord)
                    .where(AICommentRecord.analysis_id == ticket.signal.analysis_id)
                    .order_by(desc(AICommentRecord.created_at))
                    .limit(1)
                ) if ticket.signal and ticket.signal.analysis_id else None

                if stmt_ai is not None:
                    ai_rec = await session.scalar(stmt_ai)
                    if ai_rec and ai_rec.content:
                        ai_comment_text = ai_rec.content.get("ringkasan")
                        break
                await asyncio.sleep(1.0)

            # Check broker calibration
            cal = await get_latest_broker_calibration(session, ticket.symbol)
            if cal:
                ticket.broker_offset = cal.offset

            # Check confirmation by Strategy B
            confirmed_by_b = bool(ticket.signal and ticket.signal.confirmed_by_b)

            levels = {
                "entry": ticket.entry,
                "sl": ticket.sl,
                "tp1": ticket.tp1,
                "tp2": ticket.tp2,
            }

            # Render Chart PNG
            chart_bytes: bytes | None = None
            if self.settings.app.telegram.send_chart_image:
                try:
                    chart_bytes = await load_candles_and_render_chart(
                        session=session,
                        symbol=ticket.symbol,
                        tf="M15",
                        levels=levels,
                        limit=60,
                    )
                except Exception as exc:
                    logger.error("ticket_chart_render_failed", error=str(exc))

        # Build inline keyboard: [✅ Saya eksekusi] [⏭ Lewati] [📊 Detail]
        keyboard = [
            [
                InlineKeyboardButton("✅ Saya eksekusi", callback_data=f"exec:{ticket.id}"),
                InlineKeyboardButton("⏭ Lewati", callback_data=f"skip:{ticket.id}"),
                InlineKeyboardButton("📊 Detail", callback_data=f"detail:{ticket.id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        caption = format_ticket_message(
            ticket=ticket,
            ai_comment=ai_comment_text,
            confirmed_by_b=confirmed_by_b,
        )

        if chart_bytes:
            await self.broadcast_photo(
                photo_bytes=chart_bytes,
                caption=caption,
                reply_markup=reply_markup,
            )
        else:
            await self.broadcast_message(text=caption, reply_markup=reply_markup)

    async def notify_paper_exit(self, trade_data: dict[str, Any]) -> None:
        """Send notification for paper trading exits (TP1/TP2/SL/time stop/opposite)."""
        reason = trade_data.get("exit_reason") or ("TP1" if trade_data.get("tp1_hit") else "CLOSED")
        msg = format_paper_exit_notification(trade_data, reason)
        await self.broadcast_message(text=msg)

    async def notify_ticket_expired(self, ticket_id: int, symbol: str, reason: str) -> None:
        """Send notification when a ticket expires."""
        msg = format_ticket_expired_notification(ticket_id, symbol, reason)
        await self.broadcast_message(text=msg)

    async def notify_brief(self, brief_data: dict[str, Any], kind: str = "morning") -> None:
        """Send scheduled Market Brief notification."""
        msg = format_brief_message(brief_data, kind=kind)
        await self.broadcast_message(text=msg)

    async def notify_daily_recap(self) -> None:
        """Send 22:00 WIB daily performance summary."""
        now_wib = utc_now().astimezone(WIB)
        date_str = now_wib.strftime("%d-%m-%Y")
        start_day_utc = now_wib.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)

        async with get_db_session() as session:
            # Paper trades closed today
            p_stmt = select(PaperTradeRecord).where(
                (PaperTradeRecord.is_virtual == False)  # noqa: E712
                & (PaperTradeRecord.status == "CLOSED")
                & (PaperTradeRecord.exit_time >= start_day_utc)
            )
            paper_today = list((await session.execute(p_stmt)).scalars().all())

            # Real executions completed today
            r_stmt = select(RealExecutionRecord).where(
                (RealExecutionRecord.exit_price.isnot(None))
                & (RealExecutionRecord.exit_time >= start_day_utc)
            )
            real_today = list((await session.execute(r_stmt)).scalars().all())

        msg = format_daily_recap_message(
            date_str=date_str,
            paper_trades=paper_today,
            real_executions=real_today,
        )
        await self.broadcast_message(text=msg)

    async def notify_system_status(self, service: str, status: str, details: str = "") -> None:
        """Send system alert when a service degrades or recovers."""
        msg = format_system_status_notification(service, status, details)
        await self.broadcast_message(text=msg)


async def run_signals_consumer(notifier: TelegramNotifier) -> None:
    """Consume Redis Stream `signals` with consumer group `telegram`."""
    redis = get_redis_client()
    group_name = "telegram"
    consumer_name = "tg_worker_1"

    try:
        await redis.xgroup_create(STREAM_SIGNALS, group_name, id="0", mkstream=True)
    except Exception:
        # Group likely already exists
        pass

    logger.info("telegram_signals_consumer_started", stream=STREAM_SIGNALS, group=group_name)

    while True:
        try:
            entries = await redis.xreadgroup(
                groupname=group_name,
                consumername=consumer_name,
                streams={STREAM_SIGNALS: ">"},
                count=10,
                block=3000,
            )
            if not entries:
                continue

            for _stream_name, messages in entries:
                for message_id, raw_fields in messages:
                    try:
                        raw_data = raw_fields.get("data")
                        if raw_data:
                            evt = SignalEvent.model_validate_json(raw_data)
                            if evt.ticket_id:
                                logger.info(
                                    "dispatching_ticket_notification",
                                    ticket_id=evt.ticket_id,
                                    symbol=evt.symbol,
                                )
                                await notifier.notify_ticket(evt.ticket_id)
                        await redis.xack(STREAM_SIGNALS, group_name, message_id)
                    except Exception as exc:
                        logger.error("error_handling_signal_event", error=str(exc))
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("telegram_signals_consumer_error", error=str(exc))
            await asyncio.sleep(2.0)


async def run_ui_events_consumer(notifier: TelegramNotifier) -> None:
    """Consume Pub/Sub channel `ui.events` for paper exits, ticket expiration, and recaps."""
    redis = get_redis_client()
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL_UI_EVENTS)

    logger.info("telegram_ui_events_consumer_started", channel=CHANNEL_UI_EVENTS)

    while True:
        try:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=2.0)
            if not msg or msg.get("type") != "message":
                await asyncio.sleep(0.5)
                continue

            raw_data = msg.get("data")
            if not raw_data:
                continue

            try:
                evt_dict = json.loads(raw_data)
                evt_type = evt_dict.get("type")
                data = evt_dict.get("data", {})

                if evt_type == "paper_trade":
                    status = data.get("status")
                    tp1_hit = data.get("tp1_hit")
                    if status == "CLOSED" or tp1_hit:
                        await notifier.notify_paper_exit(data)

                elif evt_type == "ticket":
                    if data.get("status") == "expired":
                        await notifier.notify_ticket_expired(
                            ticket_id=data.get("id", 0),
                            symbol=data.get("symbol", ""),
                            reason=data.get("reason", "EXPIRED_TIME"),
                        )

                elif evt_type == "brief":
                    kind = data.get("kind", "morning")
                    await notifier.notify_brief(data, kind=kind)

                elif evt_type == "daily_recap":
                    await notifier.notify_daily_recap()

                elif evt_type == "system_status":
                    await notifier.notify_system_status(
                        service=data.get("service", "core"),
                        status=data.get("status", "healthy"),
                        details=data.get("details", ""),
                    )

            except Exception as exc:
                logger.error("error_handling_ui_event_for_telegram", error=str(exc))

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("telegram_ui_events_consumer_error", error=str(exc))
            await asyncio.sleep(2.0)

    await pubsub.unsubscribe(CHANNEL_UI_EVENTS)
