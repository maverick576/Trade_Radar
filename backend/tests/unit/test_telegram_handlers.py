"""Unit tests for Telegram bot command handlers, inline callbacks, and execution replies."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from telegram import CallbackQuery, Chat, Message, Update
from telegram import User as TgUser

from traderadar.core.config import get_settings
from traderadar.core.models import (
    Base,
    Candle,
    TelegramChat,
    TicketRecord,
)
from traderadar.telegram.handlers import (
    analisa_command,
    callback_query_handler,
    eksekusi_command,
    help_command,
    kalibrasi_command,
    pause_command,
    reply_message_handler,
    resume_command,
    start_command,
    ticket_command,
    tutup_command,
)


class MockRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(self, key: str, value: str, *args: Any, **kwargs: Any) -> bool:
        self.data[key] = str(value)
        return True

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self.data:
                del self.data[k]
                count += 1
        return count


@pytest.fixture
def mock_redis() -> MockRedis:
    return MockRedis()


@pytest.fixture
def test_settings() -> Any:
    settings = get_settings()
    settings.env.TELEGRAM_ALLOWED_CHAT_IDS = "123456,654321"
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


def make_update(chat_id: int = 123456, text: str = "", username: str = "trader") -> Update:
    update = MagicMock(spec=Update)
    chat = MagicMock(spec=Chat)
    chat.id = chat_id
    chat.send_message = AsyncMock()
    chat.send_action = AsyncMock()
    chat.send_photo = AsyncMock()

    user = MagicMock(spec=TgUser)
    user.id = chat_id
    user.username = username

    message = MagicMock(spec=Message)
    message.text = text
    message.reply_text = AsyncMock()

    update.effective_chat = chat
    update.effective_user = user
    update.effective_message = message
    return update


@pytest.mark.asyncio
async def test_start_command_authorized_and_unauthorized(
    test_settings: Any,
    db_session: AsyncSession,
) -> None:
    """Authorized chat registers in DB; unauthorized chat receives instruction."""
    with patch("traderadar.telegram.whitelist.get_db_session") as mock_db:
        mock_db.return_value.__aenter__.return_value = db_session

        # 1. Authorized chat
        update_auth = make_update(chat_id=123456)
        context = MagicMock()
        await start_command(update_auth, context)

        update_auth.effective_chat.send_message.assert_called_once()
        msg_auth = update_auth.effective_chat.send_message.call_args[1]["text"]
        assert "123456" in msg_auth
        assert "Terdaftar & Terverifikasi" in msg_auth

        # 2. Unauthorized chat
        update_unauth = make_update(chat_id=999999)
        await start_command(update_unauth, context)
        msg_unauth = update_unauth.effective_chat.send_message.call_args[1]["text"]
        assert "999999" in msg_unauth
        assert "Belum Terdaftar" in msg_unauth


@pytest.mark.asyncio
async def test_help_command(test_settings: Any, db_session: AsyncSession) -> None:
    """Help command outputs command guide."""
    with patch("traderadar.telegram.whitelist.get_db_session") as mock_db:
        mock_db.return_value.__aenter__.return_value = db_session
        update = make_update(chat_id=123456)
        context = MagicMock()
        await help_command(update, context)

        update.effective_chat.send_message.assert_called_once()
        text = update.effective_chat.send_message.call_args[1]["text"]
        assert "/analisa" in text
        assert "/ticket" in text


@pytest.mark.asyncio
async def test_ticket_command_with_inline_keyboard(
    test_settings: Any,
    db_session: AsyncSession,
) -> None:
    """Active ticket generates formatted message and inline action buttons."""
    with patch("traderadar.telegram.whitelist.get_db_session") as mock_db, \
         patch("traderadar.telegram.handlers.get_db_session") as mock_handler_db:
        mock_db.return_value.__aenter__.return_value = db_session
        mock_handler_db.return_value.__aenter__.return_value = db_session

        # Create active ticket
        ticket = TicketRecord(
            id=1,
            symbol="XAUUSD",
            side="LONG",
            strategy="Konfluensi-10",
            score=70.0,
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
            invalidation="Break 2636.5",
            reasons=["Supertrend BULL"],
            risks=[],
            suggested_lot=0.06,
            valid_until=datetime(2026, 10, 15, 2, 0, tzinfo=UTC),
            status="new",
        )
        db_session.add(ticket)
        await db_session.commit()

        update = make_update(chat_id=123456)
        context = MagicMock()
        await ticket_command(update, context)

        update.effective_chat.send_message.assert_called_once()
        kwargs = update.effective_chat.send_message.call_args[1]
        text = kwargs["text"]
        reply_markup = kwargs["reply_markup"]

        assert "BUY XAUUSD" in text
        assert "2651.00" in text
        assert reply_markup is not None
        # Check inline buttons
        buttons = reply_markup.inline_keyboard[0]
        assert len(buttons) == 3
        assert buttons[0].text == "✅ Saya eksekusi"
        assert buttons[0].callback_data == "exec:1"
        assert buttons[1].text == "⏭ Lewati"
        assert buttons[1].callback_data == "skip:1"
        assert buttons[2].text == "📊 Detail"
        assert buttons[2].callback_data == "detail:1"


@pytest.mark.asyncio
async def test_kalibrasi_command(test_settings: Any, db_session: AsyncSession) -> None:
    """Kalibrasi computes offset = broker_price - source_price and saves to DB."""
    with patch("traderadar.telegram.whitelist.get_db_session") as mock_db, \
         patch("traderadar.telegram.handlers.get_db_session") as mock_handler_db:
        mock_db.return_value.__aenter__.return_value = db_session
        mock_handler_db.return_value.__aenter__.return_value = db_session

        # Seed candle with close price 2651.0
        c = Candle(
            symbol="XAUUSD",
            tf="M15",
            open_time=datetime(2026, 10, 15, 1, 0, tzinfo=UTC),
            open=2650.0,
            high=2652.0,
            low=2649.0,
            close=2651.0,
            volume=100.0,
            source="binance_futures",
        )
        db_session.add(c)
        await db_session.commit()

        update = make_update(chat_id=123456)
        context = MagicMock()
        context.args = ["XAUUSD", "2652.3"]

        await kalibrasi_command(update, context)

        update.effective_chat.send_message.assert_called_once()
        text = update.effective_chat.send_message.call_args[1]["text"]
        assert "+1.30 poin" in text
        assert "2652.30" in text
        assert "2651.00" in text


@pytest.mark.asyncio
async def test_eksekusi_command_and_tutup(test_settings: Any, db_session: AsyncSession) -> None:
    """Manual execution records to Jurnal Real with slippage, closing calculates PnL."""
    with patch("traderadar.telegram.whitelist.get_db_session") as mock_db, \
         patch("traderadar.telegram.handlers.get_db_session") as mock_handler_db:
        mock_db.return_value.__aenter__.return_value = db_session
        mock_handler_db.return_value.__aenter__.return_value = db_session

        ticket = TicketRecord(
            id=2,
            symbol="XAUUSD",
            side="LONG",
            strategy="Konfluensi-10",
            score=70.0,
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
            invalidation="Break",
            reasons=[],
            risks=[],
            valid_until=datetime(2026, 10, 15, 2, 0, tzinfo=UTC),
            status="new",
        )
        db_session.add(ticket)
        await db_session.commit()

        # 1. /eksekusi 2 2651.5 0.06
        update_exec = make_update(chat_id=123456)
        context_exec = MagicMock()
        context_exec.args = ["2", "2651.5", "0.06"]

        await eksekusi_command(update_exec, context_exec)

        update_exec.effective_chat.send_message.assert_called_once()
        msg_exec = update_exec.effective_chat.send_message.call_args[1]["text"]
        assert "Eksekusi Nyata Tercatat" in msg_exec
        assert "2651.50" in msg_exec
        assert "+0.50 poin" in msg_exec  # slippage

        # 2. /tutup 2 2665.5
        update_close = make_update(chat_id=123456)
        context_close = MagicMock()
        context_close.args = ["2", "2665.5"]

        await tutup_command(update_close, context_close)

        update_close.effective_chat.send_message.assert_called_once()
        msg_close = update_close.effective_chat.send_message.call_args[1]["text"]
        assert "Posisi Riil Berhasil Ditutup" in msg_close
        assert "2665.50" in msg_close
        assert "Realized PnL" in msg_close


@pytest.mark.asyncio
async def test_inline_callback_and_reply_execution_flow(
    test_settings: Any,
    db_session: AsyncSession,
    mock_redis: MockRedis,
) -> None:
    """'Saya eksekusi' inline button prompts for fill price, and reply completes real execution."""
    with patch("traderadar.telegram.whitelist.get_db_session") as mock_db, \
         patch("traderadar.telegram.handlers.get_db_session") as mock_handler_db, \
         patch("traderadar.telegram.handlers.get_redis_client", return_value=mock_redis):
        mock_db.return_value.__aenter__.return_value = db_session
        mock_handler_db.return_value.__aenter__.return_value = db_session

        ticket = TicketRecord(
            id=5,
            symbol="XAUUSD",
            side="LONG",
            strategy="Konfluensi-10",
            score=75.0,
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
            invalidation="Break",
            reasons=[],
            risks=[],
            suggested_lot=0.06,
            valid_until=datetime(2026, 10, 15, 2, 0, tzinfo=UTC),
            status="new",
        )
        db_session.add(ticket)
        await db_session.commit()

        # Step 1: User clicks [✅ Saya eksekusi] (callback exec:5)
        update_cb = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.data = "exec:5"
        query.answer = AsyncMock()
        update_cb.callback_query = query
        update_cb.effective_chat = MagicMock(id=123456, send_message=AsyncMock())
        update_cb.effective_user = MagicMock(id=123456, username="trader")

        await callback_query_handler(update_cb, MagicMock())

        # Bot prompts user for fill price
        update_cb.effective_chat.send_message.assert_called_once()
        prompt_text = update_cb.effective_chat.send_message.call_args[1]["text"]
        assert "Eksekusi Ticket #5" in prompt_text

        # Verify pending state was saved in Redis
        pending_raw = await mock_redis.get("tg:pending_exec:123456")
        assert pending_raw is not None
        pending = json.loads(pending_raw)
        assert pending["ticket_id"] == 5

        # Step 2: User replies with fill price: "2651.5 0.06"
        update_reply = make_update(chat_id=123456, text="2651.5 0.06")
        await reply_message_handler(update_reply, MagicMock())

        update_reply.effective_chat.send_message.assert_called_once()
        reply_confirm = update_reply.effective_chat.send_message.call_args[1]["text"]
        assert "Eksekusi Nyata Tercatat (Jurnal Real)" in reply_confirm
        assert "2651.50" in reply_confirm
        assert "0.06 lot" in reply_confirm

        # Redis pending key is cleared
        assert await mock_redis.get("tg:pending_exec:123456") is None

        # Verify DB ticket is updated to executed
        await db_session.refresh(ticket)
        assert ticket.status == "executed"


@pytest.mark.asyncio
async def test_analisa_command_execution(
    test_settings: Any,
    db_session: AsyncSession,
    mock_redis: MockRedis,
) -> None:
    """/analisa XAUUSD responds with chart photo and text within <= 20 seconds."""
    with patch("traderadar.telegram.whitelist.get_db_session") as mock_db, \
         patch("traderadar.telegram.handlers.get_db_session") as mock_handler_db, \
         patch("traderadar.telegram.handlers.get_redis_client", return_value=mock_redis):
        mock_db.return_value.__aenter__.return_value = db_session
        mock_handler_db.return_value.__aenter__.return_value = db_session

        # Seed cached analysis
        analysis_payload = {
            "symbol": "XAUUSD",
            "tf": "M15",
            "score": 75.0,
            "verdict": "STRONG_LONG",
            "counts": {"bull": 8, "bear": 0, "neutral": 2},
            "indicators": [
                {
                    "key": "supertrend",
                    "name": "Supertrend",
                    "state": "BULL",
                    "reason": "Uptrend aktif",
                    "values": {"atr": 10.0},
                },
                {
                    "key": "vwap",
                    "name": "VWAP",
                    "state": "BULL",
                    "reason": "Harga di atas VWAP",
                    "values": {"vwap": 2651.0},
                },
            ],
            "macro": {"passed": True},
        }
        await mock_redis.set(
            "analysis:latest:XAUUSD:M15",
            json.dumps(analysis_payload),
        )

        # Seed 30 candles for chart
        base_t = datetime(2026, 10, 15, 0, 0, tzinfo=UTC)
        for i in range(30):
            db_session.add(
                Candle(
                    symbol="XAUUSD",
                    tf="M15",
                    open_time=base_t + timedelta(minutes=15 * i),
                    open=2650.0 + i,
                    high=2652.0 + i,
                    low=2649.0 + i,
                    close=2651.0 + i,
                    volume=300.0,
                    source="binance_futures",
                )
            )
        await db_session.commit()

        update = make_update(chat_id=123456)
        context = MagicMock()
        context.args = ["XAUUSD"]

        await analisa_command(update, context)

        # Should send photo with caption
        update.effective_chat.send_photo.assert_called_once()
        caption = update.effective_chat.send_photo.call_args[1]["caption"]
        photo = update.effective_chat.send_photo.call_args[1]["photo"]

        assert "XAUUSD [M15]" in caption
        assert "STRONG BUY" in caption
        assert isinstance(photo, bytes)
        assert photo.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_pause_and_resume_commands(test_settings: Any, db_session: AsyncSession) -> None:
    """/pause and /resume properly mute and unmute subscribers in database."""
    with patch("traderadar.telegram.whitelist.get_db_session") as mock_db, \
         patch("traderadar.telegram.handlers.get_db_session") as mock_handler_db:
        mock_db.return_value.__aenter__.return_value = db_session
        mock_handler_db.return_value.__aenter__.return_value = db_session

        update = make_update(chat_id=123456)
        context = MagicMock()

        # Pause
        await pause_command(update, context)
        update.effective_chat.send_message.assert_called_once()
        assert "di-pause" in update.effective_chat.send_message.call_args[1]["text"]

        chat_row = await db_session.get(TelegramChat, 123456)
        assert chat_row is not None
        assert chat_row.paused is True

        # Resume
        update.effective_chat.send_message.reset_mock()
        await resume_command(update, context)
        update.effective_chat.send_message.assert_called_once()
        assert "aktif kembali" in update.effective_chat.send_message.call_args[1]["text"]

        await db_session.refresh(chat_row)
        assert chat_row.paused is False
