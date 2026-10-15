"""Two-way command and callback query handlers for TradeRadar Telegram Bot.

Implements all commands from BLUEPRINT.md §5.8 and ROADMAP.md Phase 7:
/start, /help, /brief, /analisa, /ticket, /kalibrasi, /eksekusi, /tutup,
/posisi, /winrate, /kalender, /pause, /resume, plus interactive inline button workflows.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import desc, select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from traderadar.ai.brief import generate_market_brief
from traderadar.ai.service import AIService
from traderadar.core.config import get_settings
from traderadar.core.db import get_db_session
from traderadar.core.logging import get_logger
from traderadar.core.models import (
    AICommentRecord,
    AnalysisRecord,
    Candle,
    MarketBriefRecord,
    TicketRecord,
)
from traderadar.core.redis import get_redis_client
from traderadar.core.time import to_wib, utc_now
from traderadar.services.paper_store import get_open_paper_trades
from traderadar.services.ticket_store import (
    close_real_execution,
    get_latest_broker_calibration,
    get_ticket_by_id,
    get_tickets,
    record_execution,
    save_broker_calibration,
    update_ticket_status,
)
from traderadar.stats.service import get_journal_stats
from traderadar.telegram.charts import load_candles_and_render_chart
from traderadar.telegram.formatters import (
    format_analysis_message,
    format_brief_message,
    format_calendar_news,
    format_help_message,
    format_paper_positions,
    format_start_message,
    format_ticket_detail_message,
    format_ticket_message,
    format_winrate_stats,
)
from traderadar.telegram.whitelist import (
    get_or_create_chat,
    is_chat_allowed,
    set_chat_paused,
    whitelist_only,
)

logger = get_logger("traderadar.telegram.handlers")
WIB = ZoneInfo("Asia/Jakarta")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start: Greeting + Chat ID + Authorization status + Disclaimer."""
    chat = update.effective_chat
    if not chat:
        return

    allowed = is_chat_allowed(chat.id)
    if allowed:
        try:
            username = update.effective_user.username if update.effective_user else None
            async with get_db_session() as session:
                await get_or_create_chat(session, chat.id, username)
        except Exception as exc:
            logger.error("start_registration_error", error=str(exc))

    text = format_start_message(chat_id=chat.id, is_allowed=allowed)
    await chat.send_message(text=text, parse_mode=ParseMode.MARKDOWN)


@whitelist_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help: List all commands with usage guidance in Indonesian."""
    if not update.effective_chat:
        return
    text = format_help_message()
    await update.effective_chat.send_message(text=text, parse_mode=ParseMode.MARKDOWN)


@whitelist_only
async def brief_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /brief: Fetch latest Market Brief or generate on-demand."""
    chat = update.effective_chat
    if not chat:
        return

    await chat.send_action(action=ChatAction.TYPING)
    settings = get_settings()

    async with get_db_session() as session:
        # Check latest saved brief
        stmt = select(MarketBriefRecord).order_by(desc(MarketBriefRecord.generated_at)).limit(1)
        brief_rec = await session.scalar(stmt)

        if not brief_rec:
            # Generate on demand
            try:
                redis_client = get_redis_client()
                ai_service = AIService(settings=settings, redis_client=redis_client)
                narrative, brief_rec = await generate_market_brief(
                    session=session,
                    ai_service=ai_service,
                    settings=settings,
                    kind="morning",
                )
                await session.commit()
            except Exception as exc:
                logger.error("ondemand_brief_generation_error", error=str(exc))
                await chat.send_message(
                    text=(
                        "⚠️ *Gagal membuat Market Brief secara otomatis. "
                        "Silakan coba sesaat lagi.*"
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

        brief_dict = {
            "kind": brief_rec.kind,
            "generated_at": brief_rec.generated_at.isoformat(),
            "payload": brief_rec.payload,
            "narrative": brief_rec.narrative,
        }
        msg = format_brief_message(brief_dict, kind=brief_rec.kind)
        await chat.send_message(text=msg, parse_mode=ParseMode.MARKDOWN)


@whitelist_only
async def analisa_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /analisa <SIMBOL> [TF]: Technical confluence analysis + Chart PNG + AI comment."""
    chat = update.effective_chat
    if not chat:
        return

    args = context.args or []
    if not args:
        await chat.send_message(
            text=(
                "ℹ️ *Format perintah salah.*\n"
                "Gunakan: `/analisa <SIMBOL> [TF]`\n"
                "_Contoh:_ `/analisa XAUUSD` atau `/analisa BTCUSDT H1`"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    raw_symbol = args[0].strip().upper()
    tf = args[1].strip().upper() if len(args) > 1 else "M15"

    # Normalize symbol
    clean_sym = raw_symbol.replace("USDT", "").replace("_", "")
    if clean_sym in ("XAU", "GOLD"):
        clean_sym = "XAUUSD"
    elif not clean_sym.endswith("USDT") and clean_sym in ("BTC", "ETH", "SOL"):
        clean_sym = f"{clean_sym}USDT"

    await chat.send_action(action=ChatAction.UPLOAD_PHOTO)

    settings = get_settings()
    redis_client = get_redis_client()

    # 1. Fetch analysis from Redis cache or database
    analysis_dict: dict[str, Any] | None = None
    cached_bytes = await redis_client.get(f"analysis:latest:{clean_sym}:{tf}")
    if cached_bytes:
        try:
            analysis_dict = json.loads(cached_bytes)
        except Exception:
            pass

    async with get_db_session() as session:
        if not analysis_dict:
            stmt = (
                select(AnalysisRecord)
                .where(AnalysisRecord.symbol == clean_sym, AnalysisRecord.tf == tf)
                .order_by(desc(AnalysisRecord.bar_time))
                .limit(1)
            )
            rec = await session.scalar(stmt)
            if rec:
                analysis_dict = {
                    "symbol": rec.symbol,
                    "tf": rec.tf,
                    "score": rec.score,
                    "verdict": rec.verdict,
                    "counts": rec.counts,
                    "indicators": rec.indicators,
                    "category_votes": rec.category_votes,
                    "htf": rec.htf,
                    "macro": rec.macro,
                    "weights_version": rec.weights_version,
                }

        if not analysis_dict:
            await chat.send_message(
                text=f"⚠️ *Belum ada data analisis konfluensi untuk {clean_sym} [{tf}].*",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # 2. Fetch or trigger AI commentary
        ai_comment: dict[str, Any] | None = None
        stmt_ai = (
            select(AICommentRecord)
            .join(AnalysisRecord, AICommentRecord.analysis_id == AnalysisRecord.id)
            .where(AnalysisRecord.symbol == clean_sym, AnalysisRecord.tf == tf)
            .order_by(desc(AICommentRecord.created_at))
            .limit(1)
        )
        ai_rec = await session.scalar(stmt_ai)
        if ai_rec:
            ai_comment = ai_rec.content
        else:
            try:
                from traderadar.ai.schemas import AIInputPayload
                price = 0.0
                for ind in analysis_dict.get("indicators", []):
                    if ind.get("key") == "vwap" and "vwap" in ind.get("values", {}):
                        price = float(ind["values"]["vwap"])
                        break
                payload = AIInputPayload(
                    symbol=clean_sym,
                    tf=tf,
                    bar_time=str(analysis_dict.get("bar_time", utc_now().isoformat())),
                    price=price or 1.0,
                    verdict=str(analysis_dict.get("verdict", "NEUTRAL")),
                    score=float(analysis_dict.get("score", 0.0)),
                    counts=analysis_dict.get("counts", {}),
                    indicators=analysis_dict.get("indicators", []),
                    macro=analysis_dict.get("macro", {}),
                    htf=analysis_dict.get("htf", {}),
                    strategy_b=analysis_dict.get("strategy_b", {}),
                )
                ai_service = AIService(settings=settings, redis_client=redis_client)
                ai_resp = await ai_service.generate_comment(payload=payload, session=session)
                ai_comment = ai_resp.comment.model_dump()
            except Exception as exc:
                logger.warning("ondemand_ai_comment_fallback", error=str(exc))

        # 3. Check if there are active ticket levels to overlay on chart
        levels: dict[str, float] | None = None
        ticket_stmt = (
            select(TicketRecord)
            .where(TicketRecord.symbol == clean_sym, TicketRecord.status == "new")
            .order_by(desc(TicketRecord.created_at))
            .limit(1)
        )
        active_t = await session.scalar(ticket_stmt)
        if active_t:
            levels = {
                "entry": active_t.entry,
                "sl": active_t.sl,
                "tp1": active_t.tp1,
                "tp2": active_t.tp2,
            }

        # 4. Render Candlestick Chart PNG
        chart_bytes: bytes | None = None
        try:
            chart_bytes = await load_candles_and_render_chart(
                session=session,
                symbol=clean_sym,
                tf=tf,
                levels=levels,
                limit=60,
            )
        except Exception as exc:
            logger.error("chart_rendering_failed", error=str(exc))

    caption = format_analysis_message(analysis_dict, symbol=clean_sym, tf=tf, ai_comment=ai_comment)

    # 5. Send Photo or Text fallback
    if chart_bytes:
        await chat.send_photo(
            photo=chart_bytes,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await chat.send_message(text=caption, parse_mode=ParseMode.MARKDOWN)


@whitelist_only
async def ticket_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ticket: List active trade tickets with inline action buttons."""
    chat = update.effective_chat
    if not chat:
        return

    async with get_db_session() as session:
        active_tickets = await get_tickets(session, status="new", limit=5)
        if not active_tickets:
            await chat.send_message(
                text="ℹ️ *Tidak ada Trade Ticket aktif yang siap dieksekusi saat ini.*",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        for t in active_tickets:
            # Check calibration
            cal = await get_latest_broker_calibration(session, t.symbol)
            if cal:
                t.broker_offset = cal.offset

            # Check if confirmed by Strategy B
            confirmed_by_b = False
            if t.signal:
                confirmed_by_b = t.signal.confirmed_by_b

            msg = format_ticket_message(t, confirmed_by_b=confirmed_by_b)

            # Interactive inline buttons
            keyboard = [
                [
                    InlineKeyboardButton("✅ Saya eksekusi", callback_data=f"exec:{t.id}"),
                    InlineKeyboardButton("⏭ Lewati", callback_data=f"skip:{t.id}"),
                    InlineKeyboardButton("📊 Detail", callback_data=f"detail:{t.id}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await chat.send_message(
                text=msg,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN,
            )


@whitelist_only
async def kalibrasi_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /kalibrasi <SIMBOL> <harga_broker>: Set broker price offset."""
    chat = update.effective_chat
    if not chat:
        return

    args = context.args or []
    if len(args) < 2:
        await chat.send_message(
            text=(
                "ℹ️ *Format perintah salah.*\n"
                "Gunakan: `/kalibrasi <SIMBOL> <HARGA_BROKER>`\n"
                "_Contoh:_ `/kalibrasi XAUUSD 2652.3`"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    raw_symbol = args[0].strip().upper()
    clean_sym = raw_symbol.replace("USDT", "").replace("_", "")
    if clean_sym in ("XAU", "GOLD"):
        clean_sym = "XAUUSD"

    try:
        broker_price = float(args[1].replace(",", "."))
    except ValueError:
        await chat.send_message(
            text="⚠️ *Harga broker harus berupa angka desimal yang valid.*",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    async with get_db_session() as session:
        # Get source price from latest candle
        stmt = (
            select(Candle.close)
            .where(
                (Candle.symbol == clean_sym)
                | (Candle.symbol == f"{clean_sym}USDT")
                | (Candle.symbol == raw_symbol)
            )
            .order_by(desc(Candle.open_time))
            .limit(1)
        )
        source_price = await session.scalar(stmt)
        if not source_price:
            source_price = broker_price

        # Valid for 4 hours (240 minutes)
        expires_at = utc_now() + timedelta(hours=4)
        profile_name = "Telegram User Broker"

        record = await save_broker_calibration(
            session=session,
            symbol=clean_sym,
            broker_profile=profile_name,
            broker_price=broker_price,
            source_price=source_price,
            expires_at=expires_at,
        )

        offset = record.offset
        offset_sign = f"{offset:+.2f}"

        await chat.send_message(
            text=(
                f"✅ *Kalibrasi Offset Tersimpan:*\n\n"
                f"• Simbol: *{clean_sym}*\n"
                f"• Harga Broker: `{broker_price:.2f}`\n"
                f"• Harga Sumber: `{source_price:.2f}`\n"
                f"• Offset: *{offset_sign} poin* (berlaku 4 jam)\n\n"
                f"_Semua Trade Ticket untuk {clean_sym} otomatis disesuaikan "
                f"dengan level broker Anda._"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )


@whitelist_only
async def eksekusi_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /eksekusi <id> <harga> <lot>: Record manual real execution."""
    chat = update.effective_chat
    if not chat:
        return

    args = context.args or []
    if len(args) < 3:
        await chat.send_message(
            text=(
                "ℹ️ *Format perintah salah.*\n"
                "Gunakan: `/eksekusi <ID_TICKET> <HARGA_FILL> <LOT>`\n"
                "_Contoh:_ `/eksekusi 12 2651.5 0.06`"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        ticket_id = int(args[0])
        fill_price = float(args[1].replace(",", "."))
        lot = float(args[2].replace(",", "."))
    except ValueError:
        await chat.send_message(
            text="⚠️ *ID ticket, harga fill, dan lot harus berupa angka yang valid.*",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    async with get_db_session() as session:
        ticket = await get_ticket_by_id(session, ticket_id)
        if not ticket:
            await chat.send_message(
                text=f"⚠️ *Ticket #{ticket_id} tidak ditemukan.*",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        execution, updated_ticket = await record_execution(
            session=session,
            ticket_id=ticket.id,
            broker_profile="Telegram Execution",
            fill_price=fill_price,
            lot=lot,
            source="telegram",
            notes="Dieksekusi via bot Telegram",
        )

        action = "BUY" if updated_ticket.side == "LONG" else "SELL"
        slippage_sign = f"{execution.slippage_points:+.2f}"

        await chat.send_message(
            text=(
                f"✅ *Eksekusi Nyata Tercatat (Jurnal Real):*\n\n"
                f"• Ticket: *#{ticket.id} · {action} {ticket.symbol}*\n"
                f"• Fill Price: `{fill_price:.2f}`\n"
                f"• Ukuran Lot: `{lot:.2f} lot`\n"
                f"• Slippage: `{slippage_sign} poin` vs target entry `{ticket.entry:.2f}`\n\n"
                f"_Transaksi ini telah disimpan di Jurnal Real untuk pelacakan performa winrate._"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )


@whitelist_only
async def tutup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tutup <id> <harga>: Close manual execution and calculate realized PnL."""
    chat = update.effective_chat
    if not chat:
        return

    args = context.args or []
    if len(args) < 2:
        await chat.send_message(
            text=(
                "ℹ️ *Format perintah salah.*\n"
                "Gunakan: `/tutup <ID_TICKET> <HARGA_KELUAR>`\n"
                "_Contoh:_ `/tutup 12 2665.5`"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        ticket_id = int(args[0])
        exit_price = float(args[1].replace(",", "."))
    except ValueError:
        await chat.send_message(
            text="⚠️ *ID ticket dan harga keluar harus berupa angka yang valid.*",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    async with get_db_session() as session:
        try:
            execution, ticket = await close_real_execution(
                session=session,
                ticket_id=ticket_id,
                exit_price=exit_price,
                notes="Ditutup via bot Telegram",
            )
        except Exception as exc:
            await chat.send_message(
                text=f"⚠️ *Gagal menutup eksekusi:* {exc}",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        pnl_usd = execution.pnl_usd or 0.0
        pnl_r = execution.pnl_r or 0.0
        sign = "+" if pnl_usd >= 0 else "-"
        abs_usd = abs(pnl_usd)

        await chat.send_message(
            text=(
                f"🏁 *Posisi Riil Berhasil Ditutup:*\n\n"
                f"• Ticket: *#{ticket.id} · {ticket.symbol}*\n"
                f"• Harga Keluar: `{exit_price:.2f}`\n"
                f"• Realized PnL: *{sign}${abs_usd:.2f}* (*{pnl_r:+.2f} R*)\n\n"
                f"_Hasil transaksi telah diperbarui di Jurnal Real._"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )


@whitelist_only
async def posisi_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /posisi: List open paper trading positions."""
    chat = update.effective_chat
    if not chat:
        return

    async with get_db_session() as session:
        positions = await get_open_paper_trades(session, is_virtual=False)
        msg = format_paper_positions(positions)
        await chat.send_message(text=msg, parse_mode=ParseMode.MARKDOWN)


@whitelist_only
async def winrate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /winrate [7d|30d|all] [paper|real]: Journal performance metrics."""
    chat = update.effective_chat
    if not chat:
        return

    args = context.args or []
    period = "all"
    book = "paper"

    for a in args:
        val = a.lower()
        if val in ("7d", "30d", "all"):
            period = val
        elif val in ("paper", "real"):
            book = val

    async with get_db_session() as session:
        journal_res = await get_journal_stats(session=session, book=book, range_str=period)
        kpi = journal_res.kpis
        stats = {
            "total_closed_trades": kpi.total_trades,
            "winrate_pct": kpi.winrate_pct,
            "expectancy_r": kpi.expectancy_r,
            "realized_pnl_usd": kpi.total_pnl_usd,
            "profit_factor": kpi.profit_factor or 0.0,
            "note": (
                "Buku Paper Trading (simulasi deterministik)"
                if book == "paper"
                else "Buku Jurnal Eksekusi Nyata (input manual)"
            ),
        }

        msg = format_winrate_stats(stats, book=book, period=period)
        await chat.send_message(text=msg, parse_mode=ParseMode.MARKDOWN)


@whitelist_only
async def kalender_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /kalender: High-impact economic news calendar for next 48 hours."""
    chat = update.effective_chat
    if not chat:
        return

    await chat.send_action(action=ChatAction.TYPING)
    settings = get_settings()

    events: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(settings.env.NEWS_PRIMARY_URL)
            if resp.status_code == 200:
                raw_items = resp.json()
                now_utc = utc_now()
                end_utc = now_utc + timedelta(hours=48)

                for item in raw_items:
                    impact = str(item.get("impact", "")).lower()
                    if impact != "high":
                        continue

                    # Parse event date (ForexFactory format: "2026-10-15T12:30:00-04:00" or similar)
                    dt_str = item.get("date")
                    if not dt_str:
                        continue
                    try:
                        ev_dt = datetime.fromisoformat(dt_str)
                        if ev_dt.tzinfo is None:
                            ev_dt = ev_dt.replace(tzinfo=UTC)
                        else:
                            ev_dt = ev_dt.astimezone(UTC)

                        if now_utc <= ev_dt <= end_utc:
                            wib_time = to_wib(ev_dt).strftime("%d/%m %H:%M")
                            events.append(
                                {
                                    "time_wib": wib_time,
                                    "currency": item.get("country", "USD"),
                                    "title": item.get("title", ""),
                                    "forecast": item.get("forecast") or "-",
                                    "previous": item.get("previous") or "-",
                                }
                            )
                    except Exception:
                        continue
    except Exception as exc:
        logger.warning("failed_to_fetch_news_calendar", error=str(exc))

    msg = format_calendar_news(events)
    await chat.send_message(text=msg, parse_mode=ParseMode.MARKDOWN)


@whitelist_only
async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /pause: Mute notifications for this chat."""
    chat = update.effective_chat
    if not chat:
        return

    async with get_db_session() as session:
        await set_chat_paused(session, chat.id, paused=True)

    await chat.send_message(
        text=(
            "⏸ *Notifikasi di-pause.*\n"
            "Anda tidak akan menerima alert tiket atau ringkasan berkala "
            "sampai Anda mengirim `/resume`."
        ),
        parse_mode=ParseMode.MARKDOWN,
    )


@whitelist_only
async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /resume: Unmute notifications for this chat."""
    chat = update.effective_chat
    if not chat:
        return

    async with get_db_session() as session:
        await set_chat_paused(session, chat.id, paused=False)

    await chat.send_message(
        text=(
            "▶️ *Notifikasi aktif kembali.*\n"
            "Anda akan menerima pemberitahuan Trade Ticket baru, TP/SL, dan Market Brief harian."
        ),
        parse_mode=ParseMode.MARKDOWN,
    )


@whitelist_only
async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle interactive inline keyboard actions: [Saya eksekusi], [Lewati], [Detail]."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    data = query.data
    chat = update.effective_chat
    if not chat:
        return

    parts = data.split(":")
    action = parts[0]
    ticket_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

    if action == "exec":
        # Store pending execution state in Redis for this chat
        redis_client = get_redis_client()
        async with get_db_session() as session:
            t = await get_ticket_by_id(session, ticket_id)
            if not t or t.status not in ("new", "active"):
                await query.edit_message_reply_markup(reply_markup=None)
                await chat.send_message(
                    text=f"⚠️ *Ticket #{ticket_id} sudah tidak aktif atau telah dieksekusi.*",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            await redis_client.set(
                f"tg:pending_exec:{chat.id}",
                json.dumps({"ticket_id": t.id, "suggested_lot": t.suggested_lot or 0.01}),
                ex=600,  # 10 minutes expiry
            )

            prompt_text = (
                f"📝 *Eksekusi Ticket #{t.id} ({t.side} {t.symbol})*\n\n"
                f"Silakan balas pesan ini dengan harga fill dan lot yang Anda dapatkan di broker:\n"
                f"Format: `<HARGA_FILL> [LOT]`\n"
                f"_Contoh:_ `{t.entry:.2f} {t.suggested_lot or 0.01:.2f}`\n\n"
                f"_(Atau kirim langsung angka harga fill)_"
            )
            await chat.send_message(text=prompt_text, parse_mode=ParseMode.MARKDOWN)

    elif action == "skip":
        async with get_db_session() as session:
            await update_ticket_status(session, ticket_id, "skipped")
            await query.edit_message_reply_markup(reply_markup=None)
            await chat.send_message(
                text=f"⏭ *Ticket #{ticket_id} telah dilewati.*",
                parse_mode=ParseMode.MARKDOWN,
            )

    elif action == "detail":
        async with get_db_session() as session:
            t = await get_ticket_by_id(session, ticket_id)
            if t:
                msg = format_ticket_detail_message(t)
                await chat.send_message(text=msg, parse_mode=ParseMode.MARKDOWN)


@whitelist_only
async def reply_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text replies, e.g. fill price & lot for ticket execution."""
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not msg.text or not chat:
        return

    text = msg.text.strip()
    # If starting with slash, let CommandHandler process it
    if text.startswith("/"):
        return

    redis_client = get_redis_client()
    key = f"tg:pending_exec:{chat.id}"
    raw_pending = await redis_client.get(key)
    if not raw_pending:
        return

    try:
        pending = json.loads(raw_pending)
        ticket_id = pending["ticket_id"]
        default_lot = pending.get("suggested_lot", 0.01)

        # Parse text into fill_price and optional lot
        parts = text.split()
        fill_price = float(parts[0].replace(",", "."))
        lot = float(parts[1].replace(",", ".")) if len(parts) > 1 else float(default_lot)

        async with get_db_session() as session:
            ticket = await get_ticket_by_id(session, ticket_id)
            if not ticket:
                await chat.send_message(text=f"⚠️ *Ticket #{ticket_id} tidak ditemukan.*")
                await redis_client.delete(key)
                return

            execution, updated_ticket = await record_execution(
                session=session,
                ticket_id=ticket.id,
                broker_profile="Telegram Interactive",
                fill_price=fill_price,
                lot=lot,
                source="telegram",
                notes="Dieksekusi via tombol Telegram 'Saya eksekusi'",
            )

            await redis_client.delete(key)

            action = "BUY" if updated_ticket.side == "LONG" else "SELL"
            slippage_sign = f"{execution.slippage_points:+.2f}"

            await chat.send_message(
                text=(
                    f"✅ *Sukses! Eksekusi Nyata Tercatat (Jurnal Real):*\n\n"
                    f"• Ticket: *#{ticket.id} · {action} {ticket.symbol}*\n"
                    f"• Harga Fill: `{fill_price:.2f}`\n"
                    f"• Ukuran Lot: `{lot:.2f} lot`\n"
                    f"• Slippage: `{slippage_sign} poin` vs entry `{ticket.entry:.2f}`\n\n"
                    f"_Transaksi telah dicatat ke Jurnal Eksekusi Nyata._"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
    except Exception as exc:
        logger.error("error_processing_execution_reply", error=str(exc))
        await chat.send_message(
            text=(
                "⚠️ *Format tidak dikenali. Masukkan angka harga fill dan lot "
                "(contoh: `2651.5 0.06`).*"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
