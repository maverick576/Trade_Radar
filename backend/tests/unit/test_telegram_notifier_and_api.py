"""Unit tests for TelegramNotifier and Settings/Telegram API endpoints."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from traderadar.api.app import app
from traderadar.api.deps import get_db, get_redis_client
from traderadar.core.config import get_settings
from traderadar.core.models import (
    AICommentRecord,
    AnalysisRecord,
    Base,
    PaperTradeRecord,
    RealExecutionRecord,
    SignalRecord,
    TelegramChat,
    TicketRecord,
    User,
)
from traderadar.core.security import create_access_token, hash_password
from traderadar.core.time import utc_now
from traderadar.telegram.notifier import TelegramNotifier


class FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.storage.get(key)

    async def set(self, key: str, val: str, *args: Any, **kwargs: Any) -> bool:
        self.storage[key] = str(val)
        return True


@pytest_asyncio.fixture
async def notifier_db() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """In-memory SQLite sessionmaker for notifier tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    yield session_maker
    await engine.dispose()


@pytest.mark.asyncio
async def test_telegram_notifier_broadcast(notifier_db: async_sessionmaker[AsyncSession]) -> None:
    """Test broadcasting message and photo to active whitelisted chats."""
    now = utc_now()
    async with notifier_db() as session:
        # Chat 1: Active
        session.add(
            TelegramChat(
                chat_id=111,
                username="trader1",
                paused=False,
                created_at=now,
            )
        )
        # Chat 2: Paused
        session.add(
            TelegramChat(
                chat_id=222,
                username="trader2",
                paused=True,
                created_at=now,
            )
        )
        await session.commit()

    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=True)
    bot.send_photo = AsyncMock(return_value=True)

    settings = get_settings()
    settings.env.TELEGRAM_ALLOWED_CHAT_IDS = "111, 222"

    notifier = TelegramNotifier(bot=bot, settings=settings)

    with patch("traderadar.telegram.whitelist.get_db_session", return_value=notifier_db()):
        with patch("traderadar.telegram.notifier.get_db_session", return_value=notifier_db()):
            # Broadcast message
            sent_msg = await notifier.broadcast_message("Halo dari TradeRadar!")
            assert sent_msg == 1
            bot.send_message.assert_called_once()
            assert bot.send_message.call_args[1]["chat_id"] == 111

            # Broadcast photo
            sent_photo = await notifier.broadcast_photo(b"fake-bytes", "Caption foto")
            assert sent_photo == 1
            bot.send_photo.assert_called_once()
            assert bot.send_photo.call_args[1]["chat_id"] == 111


@pytest.mark.asyncio
async def test_telegram_notifier_notify_ticket_with_chart(
    notifier_db: async_sessionmaker[AsyncSession],
) -> None:
    """Test notify_ticket sending photo when chart rendering succeeds."""
    now = utc_now()
    async with notifier_db() as session:
        session.add(
            TelegramChat(
                chat_id=111,
                username="user1",
                paused=False,
                created_at=now,
            )
        )
        analysis = AnalysisRecord(
            symbol="XAUUSDT",
            tf="M15",
            bar_time=now,
            source="binance:XAUUSDT",
            score=85.0,
            verdict="STRONG_BUY",
            counts={"BULL": 8, "BEAR": 1, "NEUTRAL": 1, "NA": 0},
            indicators=[],
            category_votes={},
            htf={},
            macro={},
            strategy_b={},
            weights_version="v1",
        )
        session.add(analysis)
        await session.flush()

        signal = SignalRecord(
            symbol="XAUUSDT",
            tf="M15",
            strategy="Konfluensi-10",
            side="BUY",
            verdict="STRONG_BUY",
            bar_time=now,
            status="VALID",
            analysis_id=analysis.id,
            confirmed_by_b=True,
        )
        session.add(signal)
        await session.flush()

        ticket = TicketRecord(
            id=10,
            signal_id=signal.id,
            symbol="XAUUSDT",
            side="BUY",
            strategy="Konfluensi-10",
            score=85.0,
            source="binance:XAUUSDT",
            entry=2650.0,
            entry_low=2649.0,
            entry_high=2651.0,
            sl=2640.0,
            tp1=2665.0,
            tp2=2680.0,
            atr=10.0,
            sl_points=10.0,
            sl_atr_mult=1.0,
            tp1_points=15.0,
            tp2_points=30.0,
            invalidation="Break MA 50",
            reasons=["EMA Bullish"],
            risks=["NFP"],
            valid_until=now + timedelta(hours=1),
            status="new",
            suggested_lot=0.1,
            actual_risk_usd=100.0,
            actual_risk_pct=1.0,
            created_at=now,
        )
        session.add(ticket)

        ai_comment = AICommentRecord(
            analysis_id=analysis.id,
            provider="gemini",
            model="gemini-2.5-flash",
            content={"ringkasan": "Konfluensi kuat dengan konfirmasi EMA."},
            created_at=now,
        )
        session.add(ai_comment)
        await session.commit()

    bot = AsyncMock()
    bot.send_photo = AsyncMock(return_value=True)

    settings = get_settings()
    settings.env.TELEGRAM_ALLOWED_CHAT_IDS = "111"
    settings.app.telegram.wait_ai_seconds = 1
    settings.app.telegram.send_chart_image = True

    notifier = TelegramNotifier(bot=bot, settings=settings)

    with patch("traderadar.telegram.whitelist.get_db_session", return_value=notifier_db()):
        with patch("traderadar.telegram.notifier.get_db_session", return_value=notifier_db()):
            with patch(
                "traderadar.telegram.notifier.load_candles_and_render_chart",
                new_callable=AsyncMock,
                return_value=b"fake_chart_png_bytes",
            ):
                await notifier.notify_ticket(10)

    bot.send_photo.assert_called_once()
    call_kwargs = bot.send_photo.call_args[1]
    assert call_kwargs["chat_id"] == 111
    assert call_kwargs["photo"] == b"fake_chart_png_bytes"
    assert "XAUUSDT" in call_kwargs["caption"]
    assert "BUY" in call_kwargs["caption"]
    assert "Konfluensi kuat" in call_kwargs["caption"]
    assert call_kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_telegram_notifier_notify_ticket_fallback_text(
    notifier_db: async_sessionmaker[AsyncSession],
) -> None:
    """Test notify_ticket falls back to text broadcast when chart is disabled or fails."""
    now = utc_now()
    async with notifier_db() as session:
        session.add(
            TelegramChat(
                chat_id=111,
                username="user1",
                paused=False,
                created_at=now,
            )
        )
        ticket = TicketRecord(
            id=12,
            signal_id=None,
            symbol="BTCUSDT",
            side="SELL",
            strategy="Konfluensi-10",
            score=70.0,
            source="binance:BTCUSDT",
            entry=68000.0,
            entry_low=67900.0,
            entry_high=68100.0,
            sl=68500.0,
            tp1=67000.0,
            tp2=66000.0,
            atr=500.0,
            sl_points=500.0,
            sl_atr_mult=1.0,
            tp1_points=1000.0,
            tp2_points=2000.0,
            invalidation="Break MA",
            reasons=["EMA Bearish"],
            risks=["FOMC"],
            valid_until=now + timedelta(hours=1),
            status="new",
            suggested_lot=0.05,
            actual_risk_usd=100.0,
            actual_risk_pct=1.0,
            created_at=now,
        )
        session.add(ticket)
        await session.commit()

    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=True)

    settings = get_settings()
    settings.env.TELEGRAM_ALLOWED_CHAT_IDS = "111"
    settings.app.telegram.send_chart_image = False
    settings.app.telegram.wait_ai_seconds = 0

    notifier = TelegramNotifier(bot=bot, settings=settings)

    with patch("traderadar.telegram.whitelist.get_db_session", return_value=notifier_db()):
        with patch("traderadar.telegram.notifier.get_db_session", return_value=notifier_db()):
            await notifier.notify_ticket(12)

    bot.send_message.assert_called_once()
    call_kwargs = bot.send_message.call_args[1]
    assert call_kwargs["chat_id"] == 111
    assert "BTCUSDT" in call_kwargs["text"]
    assert "SELL" in call_kwargs["text"]


@pytest.mark.asyncio
async def test_telegram_notifier_notifications(
    notifier_db: async_sessionmaker[AsyncSession],
) -> None:
    """Test various proactive notifications (paper exit, expired, brief, recap, alert)."""
    now = utc_now()
    async with notifier_db() as session:
        session.add(
            TelegramChat(
                chat_id=111,
                username="user1",
                paused=False,
                created_at=now,
            )
        )
        ticket = TicketRecord(
            id=15,
            signal_id=None,
            symbol="BTCUSDT",
            side="BUY",
            strategy="Konfluensi-10",
            score=70.0,
            source="binance:BTCUSDT",
            entry=67000.0,
            entry_low=66900.0,
            entry_high=67100.0,
            sl=66500.0,
            tp1=68000.0,
            tp2=69000.0,
            atr=500.0,
            sl_points=500.0,
            sl_atr_mult=1.0,
            tp1_points=1000.0,
            tp2_points=2000.0,
            invalidation="Break MA",
            reasons=["EMA Bullish"],
            risks=[],
            valid_until=now + timedelta(hours=1),
            status="closed",
            created_at=now,
        )
        session.add(ticket)
        await session.flush()

        # Add a closed paper trade today
        session.add(
            PaperTradeRecord(
                symbol="XAUUSDT",
                side="BUY",
                strategy="Konfluensi-10",
                entry_price=2650.0,
                size=0.1,
                sl=2640.0,
                tp1=2665.0,
                tp2=2680.0,
                status="CLOSED",
                exit_price=2665.0,
                exit_time=now,
                exit_reason="TP1",
                pnl_usd=150.0,
                is_virtual=False,
                entry_time=now - timedelta(hours=1),
            )
        )
        # Add a closed real execution today
        session.add(
            RealExecutionRecord(
                ticket_id=ticket.id,
                broker_profile="IC Markets",
                fill_price=67000.0,
                exit_price=68000.0,
                lot=0.1,
                source="telegram",
                exit_time=now,
                pnl_usd=100.0,
                created_at=now - timedelta(hours=2),
            )
        )
        await session.commit()

    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=True)

    settings = get_settings()
    settings.env.TELEGRAM_ALLOWED_CHAT_IDS = "111"

    notifier = TelegramNotifier(bot=bot, settings=settings)

    with patch("traderadar.telegram.whitelist.get_db_session", return_value=notifier_db()):
        with patch("traderadar.telegram.notifier.get_db_session", return_value=notifier_db()):
            # 1. notify_paper_exit
            await notifier.notify_paper_exit(
                {
                    "symbol": "XAUUSDT",
                    "side": "BUY",
                    "exit_reason": "TP1",
                    "pnl": 150.0,
                    "pnl_pct": 2.5,
                }
            )
            assert bot.send_message.call_count == 1
            assert "TP1" in bot.send_message.call_args[1]["text"]

            # 2. notify_ticket_expired
            await notifier.notify_ticket_expired(10, "XAUUSDT", "Waktu tunggu habis (4 candle)")
            assert bot.send_message.call_count == 2
            assert "KEDALUWARSA" in bot.send_message.call_args[1]["text"]

            # 3. notify_brief
            await notifier.notify_brief(
                {"summary": "Isu inflasi AS menekan dolar."},
                kind="morning",
            )
            assert bot.send_message.call_count == 3
            assert "BRIEF PAGI" in bot.send_message.call_args[1]["text"]

            # 4. notify_daily_recap
            await notifier.notify_daily_recap()
            assert bot.send_message.call_count == 4
            assert "REKAP HARIAN" in bot.send_message.call_args[1]["text"]

            # 5. notify_system_status
            await notifier.notify_system_status("binance_ws", "degraded", "Koneksi terputus")
            assert bot.send_message.call_count == 5
            assert "STATUS SISTEM" in bot.send_message.call_args[1]["text"]


# =========================================================================
# Settings API Endpoints Integration Tests
# =========================================================================


@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[tuple[AsyncClient, str], None]:
    """Test client with test DB and valid user token."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    now = utc_now()
    async with session_maker() as session:
        user = User(
            id=1,
            email="admin@traderadar.local",
            password_hash=hash_password("adminpass"),
            created_at=now,
        )
        session.add(user)
        session.add(
            TelegramChat(
                chat_id=123456789,
                username="admin_tg",
                paused=False,
                created_at=now,
            )
        )
        await session.commit()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as s:
            yield s

    fake_redis = FakeRedis()

    async def override_get_redis() -> AsyncGenerator[FakeRedis, None]:
        yield fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis

    token = create_access_token(
        user_id=1,
        email="admin@traderadar.local",
        expires_delta=timedelta(hours=1),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, token

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_app_settings(api_client: tuple[AsyncClient, str]) -> None:
    """Test GET /api/settings returns general application configuration."""
    client, token = api_client
    resp = await client.get("/api/settings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "watchlist" in data
    assert "telegram" in data


@pytest.mark.asyncio
async def test_get_telegram_status(api_client: tuple[AsyncClient, str]) -> None:
    """Test GET /api/settings/telegram/status returns subscriber counts and bot status."""
    client, token = api_client
    settings = get_settings()
    settings.env.TELEGRAM_ENABLED = True
    settings.env.TELEGRAM_BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    settings.env.TELEGRAM_ALLOWED_CHAT_IDS = "123456789, 987654321"

    resp = await client.get(
        "/api/settings/telegram/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert data["configured"] is True
    assert data["allowed_chat_ids_count"] == 2
    assert data["active_chat_ids_count"] == 2  # 123456789 in DB, 987654321 not paused
    assert 123456789 in data["allowed_chat_ids"]
    assert data["status"] == "online"


@pytest.mark.asyncio
async def test_send_telegram_test_message_disabled_or_unconfigured(
    api_client: tuple[AsyncClient, str],
) -> None:
    """Test POST /api/settings/telegram/test raises 400 when disabled or token missing."""
    client, token = api_client
    settings = get_settings()

    # Disabled
    settings.env.TELEGRAM_ENABLED = False
    resp = await client.post(
        "/api/settings/telegram/test",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "dinonaktifkan" in resp.json()["error"]["message"]

    # Enabled but no token
    settings.env.TELEGRAM_ENABLED = True
    settings.env.TELEGRAM_BOT_TOKEN = ""
    resp = await client.post(
        "/api/settings/telegram/test",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "TELEGRAM_BOT_TOKEN" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_send_telegram_test_message_success(api_client: tuple[AsyncClient, str]) -> None:
    """Test POST /api/settings/telegram/test sends message to subscribers."""
    client, token = api_client
    settings = get_settings()
    settings.env.TELEGRAM_ENABLED = True
    settings.env.TELEGRAM_BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    settings.env.TELEGRAM_ALLOWED_CHAT_IDS = "123456789"

    mock_bot_app = MagicMock()
    mock_bot_app.bot.send_message = AsyncMock(return_value=True)

    with patch("traderadar.api.routers.settings.create_bot", return_value=mock_bot_app):
        resp = await client.post(
            "/api/settings/telegram/test",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["sent_count"] == 1
    assert "berhasil" in data["message"].lower()
    mock_bot_app.bot.send_message.assert_called_once()
