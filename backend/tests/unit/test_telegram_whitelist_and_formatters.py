"""Unit tests for Telegram whitelist security and Indonesian message formatters."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from telegram import Chat, Update
from telegram import User as TgUser

from traderadar.core.config import get_settings
from traderadar.core.models import (
    Base,
    PaperTradeRecord,
    TicketRecord,
)
from traderadar.telegram.formatters import (
    DISCLAIMER_TEXT,
    format_analysis_message,
    format_brief_message,
    format_daily_recap_message,
    format_help_message,
    format_paper_exit_notification,
    format_paper_positions,
    format_start_message,
    format_system_status_notification,
    format_ticket_detail_message,
    format_ticket_expired_notification,
    format_ticket_message,
    format_winrate_stats,
)
from traderadar.telegram.whitelist import (
    get_active_notification_chats,
    get_allowed_chat_ids,
    get_or_create_chat,
    is_chat_allowed,
    is_chat_paused,
    set_chat_paused,
    whitelist_only,
)


@pytest.fixture
def test_settings() -> Any:
    settings = get_settings()
    settings.env.TELEGRAM_ALLOWED_CHAT_IDS = "111222,333444, 555666 "
    return settings


@pytest.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


def test_whitelist_parsing(test_settings: Any) -> None:
    """Allowed chat IDs are correctly parsed from environment."""
    ids = get_allowed_chat_ids(test_settings)
    assert ids == {111222, 333444, 555666}

    assert is_chat_allowed(111222, test_settings) is True
    assert is_chat_allowed(333444, test_settings) is True
    assert is_chat_allowed(999999, test_settings) is False


def test_empty_whitelist() -> None:
    """Empty or unconfigured whitelist returns empty set."""
    settings = get_settings()
    settings.env.TELEGRAM_ALLOWED_CHAT_IDS = ""
    ids = get_allowed_chat_ids(settings)
    assert ids == set()
    assert is_chat_allowed(123456, settings) is False


@pytest.mark.asyncio
async def test_chat_registration_and_pause_toggle(db_session: AsyncSession) -> None:
    """Chats can be registered, retrieved, and paused/resumed in database."""
    chat = await get_or_create_chat(db_session, chat_id=123456, username="trader_john")
    assert chat.chat_id == 123456
    assert chat.username == "trader_john"
    assert chat.paused is False

    # Check paused state
    assert await is_chat_paused(db_session, 123456) is False

    # Toggle pause
    await set_chat_paused(db_session, 123456, paused=True)
    assert await is_chat_paused(db_session, 123456) is True

    # Resume
    await set_chat_paused(db_session, 123456, paused=False)
    assert await is_chat_paused(db_session, 123456) is False


@pytest.mark.asyncio
async def test_get_active_notification_chats(db_session: AsyncSession, test_settings: Any) -> None:
    """Active notification chats only include unpaused allowed subscribers."""
    # Register 111222 (active) and 333444 (paused)
    await get_or_create_chat(db_session, chat_id=111222, username="user1")
    await get_or_create_chat(db_session, chat_id=333444, username="user2")
    await set_chat_paused(db_session, chat_id=333444, paused=True)

    active = await get_active_notification_chats(db_session, test_settings)
    # 111222 is active, 333444 is paused, 555666 is unpaused allowed
    assert 111222 in active
    assert 333444 not in active
    assert 555666 in active


@pytest.mark.asyncio
async def test_whitelist_decorator_enforcement(test_settings: Any) -> None:
    """Unauthorized chats are strictly ignored without executing the handler."""
    mock_handler = AsyncMock()
    decorated = whitelist_only(mock_handler)

    # 1. Test unauthorized chat -> ignored
    unauth_update = MagicMock(spec=Update)
    unauth_chat = MagicMock(spec=Chat)
    unauth_chat.id = 999888
    unauth_update.effective_chat = unauth_chat
    unauth_update.effective_user = MagicMock(spec=TgUser, username="intruder")

    res = await decorated(unauth_update, MagicMock())
    assert res is None
    mock_handler.assert_not_called()

    # 2. Test authorized chat -> executes handler
    auth_update = MagicMock(spec=Update)
    auth_chat = MagicMock(spec=Chat)
    auth_chat.id = 111222
    auth_update.effective_chat = auth_chat
    auth_update.effective_user = MagicMock(spec=TgUser, username="authorized_user")

    await decorated(auth_update, MagicMock())
    mock_handler.assert_called_once()


def test_format_start_message() -> None:
    """Verify /start output contains Chat ID, authorization notice, and disclaimer."""
    allowed_msg = format_start_message(chat_id=12345, is_allowed=True)
    assert "12345" in allowed_msg
    assert "Terdaftar & Terverifikasi" in allowed_msg
    assert DISCLAIMER_TEXT in allowed_msg

    unauth_msg = format_start_message(chat_id=98765, is_allowed=False)
    assert "98765" in unauth_msg
    assert "Belum Terdaftar" in unauth_msg
    assert "TELEGRAM_ALLOWED_CHAT_IDS" in unauth_msg
    assert DISCLAIMER_TEXT in unauth_msg


def test_format_help_message() -> None:
    """Verify /help contains all commands in Indonesian."""
    msg = format_help_message()
    assert "/analisa" in msg
    assert "/brief" in msg
    assert "/ticket" in msg
    assert "/kalibrasi" in msg
    assert "/eksekusi" in msg
    assert "/tutup" in msg
    assert "/posisi" in msg
    assert "/winrate" in msg
    assert "/kalender" in msg
    assert "/pause" in msg
    assert "/resume" in msg


def test_format_ticket_message() -> None:
    """Verify Trade Ticket formatting with key levels, lot suggestion, and reasons."""
    ticket = TicketRecord(
        id=7,
        symbol="XAUUSD",
        side="LONG",
        strategy="Konfluensi-10",
        score=72.5,
        source="Binance XAUUSDT",
        entry=2651.0,
        entry_low=2650.0,
        entry_high=2652.0,
        sl=2636.5,
        tp1=2665.5,
        tp2=2680.0,
        atr=9.67,
        sl_points=14.5,
        sl_atr_mult=1.5,
        tp1_points=14.5,
        tp2_points=29.0,
        invalidation="Close M15 di bawah 2636.5",
        reasons=["Supertrend BULL", "EMA Ribbon selaras", "VWAP di atas rata-rata"],
        risks=["Funding rate sedikit tinggi"],
        suggested_lot=0.06,
        actual_risk_usd=87.0,
        actual_risk_pct=0.87,
        broker_offset=1.3,
        valid_until=datetime(2026, 10, 15, 2, 0, tzinfo=UTC),
        status="new",
    )

    text = format_ticket_message(
        ticket=ticket,
        ai_comment="Struktur momentum kuat menembus resistance.",
        confirmed_by_b=True,
    )
    assert "#7" in text
    assert "BUY XAUUSD" in text
    assert "Dikonfirmasi Triple-EMA" in text
    assert "2651.00" in text
    assert "2636.50" in text
    assert "2665.50" in text
    assert "0.06 lot" in text
    assert "$87.00" in text
    assert "+1.30 poin offset" in text
    assert "Struktur momentum kuat" in text


def test_format_ticket_detail_message() -> None:
    """Verify detail breakdown formatting."""
    ticket = TicketRecord(
        id=9,
        symbol="BTCUSDT",
        side="SHORT",
        strategy="Konfluensi-10",
        score=68.0,
        source="Binance fapi",
        entry=68500.0,
        entry_low=68450.0,
        entry_high=68550.0,
        sl=69200.0,
        tp1=67800.0,
        tp2=67100.0,
        atr=500.0,
        sl_points=700.0,
        sl_atr_mult=1.4,
        tp1_points=700.0,
        tp2_points=1400.0,
        invalidation="Break swing high",
        reasons=["CVD bearish divergence"],
        risks=["F&G greed level"],
        valid_until=datetime(2026, 10, 15, 4, 0, tzinfo=UTC),
        created_at=datetime(2026, 10, 15, 3, 0, tzinfo=UTC),
        status="new",
    )
    detail = format_ticket_detail_message(ticket)
    assert "#9" in detail
    assert "BTCUSDT" in detail
    assert "ATR14: 500.00" in detail
    assert "SL Distance: 700.00 pts" in detail


def test_format_analysis_and_brief() -> None:
    """Verify technical analysis and market brief formatting."""
    analysis = {
        "score": 65.0,
        "verdict": "STRONG_LONG",
        "counts": {"bull": 7, "bear": 1, "neutral": 2},
        "indicators": [
            {"key": "supertrend", "name": "Supertrend", "state": "BULL", "reason": "Tren naik"},
            {"key": "vwap", "name": "VWAP", "state": "BULL", "reason": "Di atas upper band"},
        ],
        "macro": {"passed": True},
    }
    ai_comment = {
        "bias": "BULLISH",
        "keyakinan": "Tinggi",
        "ringkasan": "Konfluensi multi-timeframe mendukung kelanjutan tren naik.",
    }
    text = format_analysis_message(analysis, symbol="XAUUSD", tf="M15", ai_comment=ai_comment)
    assert "XAUUSD [M15]" in text
    assert "STRONG BUY" in text
    assert "65.0/100" in text
    assert "Supertrend" in text
    assert "BULLISH" in text

    brief = {
        "payload": {
            "macro_sentiment": "Risk-on",
            "symbols": {
                "XAUUSD": {"current_price": 2652.0, "vwap_yesterday": 2645.0, "score": 68.0},
            },
        },
        "narrative": {
            "ringkasan_umum": "Pasar bergerak optimis menjelang pembukaan sesi Eropa.",
            "simbol": {
                "XAUUSD": {"bias": "Bullish", "skenario": "Fokus buy saat retest VWAP."},
            },
        },
    }
    brief_text = format_brief_message(brief, kind="morning")
    assert "MARKET BRIEF PAGI" in brief_text
    assert "Risk-on" in brief_text
    assert "2652.00" in brief_text
    assert "Fokus buy saat retest VWAP." in brief_text


def test_format_paper_positions_and_winrate() -> None:
    """Verify open positions and winrate journal metrics formatting."""
    pos = PaperTradeRecord(
        id=1,
        symbol="XAUUSD",
        side="LONG",
        entry_price=2651.0,
        entry_time=datetime(2026, 10, 15, 1, 0, tzinfo=UTC),
        size=0.06,
        sl=2636.5,
        tp1=2665.5,
        tp2=2680.0,
        tp1_hit=True,
        bars_held=8,
        status="OPEN",
    )
    pos_text = format_paper_positions([pos])
    assert "POSISI PAPER TRADING TERBUKA (1)" in pos_text
    assert "2651.00" in pos_text
    assert "TP1 tercapai (SL di BE)" in pos_text

    stats = {
        "total_closed_trades": 25,
        "winrate_pct": 68.0,
        "expectancy_r": 0.85,
        "profit_factor": 2.15,
        "realized_pnl_usd": 1420.50,
        "note": "Buku Paper Trading",
    }
    stats_text = format_winrate_stats(stats, book="paper", period="30d")
    assert "STATISTIK JURNAL · PAPER TRADING" in stats_text
    assert "30D" in stats_text
    assert "68.0%" in stats_text
    assert "+0.85 R" in stats_text
    assert "$1420.50" in stats_text


def test_format_notifications() -> None:
    """Verify alert notifications for exits, expirations, and status."""
    exit_msg = format_paper_exit_notification({"symbol": "XAUUSD", "side": "LONG"}, reason="TP1")
    assert "TARGET TP1 TERCAPAI" in exit_msg
    assert "Stop Loss telah digeser ke titik Breakeven" in exit_msg

    tp2_msg = format_paper_exit_notification(
        {"symbol": "XAUUSD", "side": "LONG", "pnl_usd": 85.0, "pnl_r": 2.0}, reason="TP2"
    )
    assert "TARGET TP2 TERCAPAI" in tp2_msg
    assert "$85.00" in tp2_msg

    exp_msg = format_ticket_expired_notification(
        ticket_id=14, symbol="BTCUSDT", reason="EXPIRED_TIME"
    )
    assert "TICKET #14 KEDALUWARSA" in exp_msg
    assert "45 mnt" in exp_msg

    status_msg = format_system_status_notification(
        service="binance",
        status="degraded",
        details="WS ping timeout",
    )
    assert "STATUS SISTEM · BINANCE" in status_msg
    assert "DEGRADED" in status_msg

    recap_msg = format_daily_recap_message(
        date_str="15-10-2026",
        paper_trades=[
            MagicMock(pnl_r=1.5, pnl_usd=50.0),
            MagicMock(pnl_r=-1.0, pnl_usd=-30.0),
        ],
        real_executions=[MagicMock(pnl_r=1.2, pnl_usd=75.0)],
    )
    assert "REKAP HARIAN TRADERADAR (22:00 WIB)" in recap_msg
    assert "15-10-2026" in recap_msg
    assert "2 trade" in recap_msg
    assert "1 trade" in recap_msg
