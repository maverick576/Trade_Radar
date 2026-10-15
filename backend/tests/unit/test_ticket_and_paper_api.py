"""Integration tests for Trade Ticket, Broker Calibration, and Paper Trading endpoints."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from traderadar.api.app import app
from traderadar.api.deps import get_db, get_redis_client
from traderadar.core.models import (
    Base,
    Candle,
    PaperTradeRecord,
    TicketRecord,
    User,
)
from traderadar.core.security import create_access_token, hash_password
from traderadar.core.time import utc_now


class FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.storage.get(key)

    async def set(self, key: str, val: str, *args: Any, **kwargs: Any) -> bool:
        self.storage[key] = str(val)
        return True


@pytest_asyncio.fixture
async def ticket_client() -> AsyncGenerator[AsyncClient, None]:
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

    fake_redis = FakeRedis()
    now = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)

    async with session_maker() as session:
        admin = User(
            id=1,
            email="admin@example.com",
            password_hash=hash_password("Password123!"),
            created_at=utc_now(),
        )
        session.add(admin)

        # Seed candle for calibration source price lookup
        candle = Candle(
            symbol="XAUUSDT",
            tf="M15",
            open_time=now,
            open=2650.0,
            high=2655.0,
            low=2648.0,
            close=2651.0,
            volume=100.0,
            source="binance_futures:XAUUSDT",
        )
        session.add(candle)

        # Seed a TicketRecord
        ticket = TicketRecord(
            id=1,
            symbol="XAUUSD",
            side="LONG",
            strategy="Konfluensi-10",
            score=62.0,
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
            invalidation="close M15 di bawah 2640.0",
            reasons=["EMA ribbon bullish", "CVD naik"],
            risks=["RSI dekat overbought"],
            valid_until=now + timedelta(minutes=45),
            status="new",
            broker_profile="Exness Standard",
            suggested_lot=0.06,
            actual_risk_usd=87.0,
            actual_risk_pct=0.87,
            min_lot_warning=False,
            created_at=now,
            updated_at=now,
        )
        session.add(ticket)

        # Seed an open PaperTradeRecord
        paper = PaperTradeRecord(
            id=1,
            ticket_id=1,
            strategy="konfluensi10",
            symbol="XAUUSD",
            side="LONG",
            entry_time=now,
            entry_price=2651.0,
            size=0.69,
            sl=2636.5,
            tp1=2665.5,
            tp2=2680.0,
            tp1_hit=False,
            bars_held=2,
            status="OPEN",
            fees_usd=1.83,
            is_virtual=False,
            created_at=now,
            updated_at=now,
        )
        session.add(paper)

        await session.commit()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as sess:
            yield sess

    async def override_get_redis() -> FakeRedis:
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = create_access_token(user_id=1, email="admin@example.com")
        client.cookies.set("access_token", token)
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_list_and_get_ticket(ticket_client: AsyncClient) -> None:
    """Test GET /api/tickets and GET /api/tickets/{id}."""
    resp = await ticket_client.get("/api/tickets")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    t = data[0]
    assert t["id"] == 1
    assert t["symbol"] == "XAUUSD"
    assert t["entry"] == 2651.0
    assert "🟢 BUY XAUUSD" in t["text_full"]
    assert "BUY XAUUSD 2651" in t["text_compact"]

    # Single get
    resp_single = await ticket_client.get("/api/tickets/1")
    assert resp_single.status_code == 200
    assert resp_single.json()["id"] == 1


@pytest.mark.asyncio
async def test_execute_and_close_ticket(ticket_client: AsyncClient) -> None:
    """Test manual execution and close cycle for a ticket."""
    # 1. Execute ticket
    exec_resp = await ticket_client.post(
        "/api/tickets/1/execute",
        json={
            "broker_profile": "Exness Standard",
            "fill_price": 2652.0,  # 1.0 point slippage
            "lot": 0.06,
            "source": "ui",
            "notes": "Executed on Exness app",
        },
    )
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["ticket_id"] == 1
    assert exec_data["fill_price"] == 2652.0
    assert exec_data["lot"] == 0.06
    assert exec_data["slippage_points"] == 1.0

    # Verify ticket status updated to executed
    t_resp = await ticket_client.get("/api/tickets/1")
    assert t_resp.json()["status"] == "executed"

    # 2. Close execution at 2665.0 (+13 points profit)
    close_resp = await ticket_client.post(
        "/api/tickets/1/close",
        json={
            "exit_price": 2665.0,
            "notes": "Closed near TP1",
        },
    )
    assert close_resp.status_code == 200
    close_data = close_resp.json()
    assert close_data["exit_price"] == 2665.0
    # Profit: 0.06 * 100 * (2665.0 - 2652.0) = 0.06 * 100 * 13 = $78.0
    assert close_data["pnl_usd"] == 78.0
    assert close_data["pnl_r"] > 0

    # Verify ticket status updated to closed
    t_resp_closed = await ticket_client.get("/api/tickets/1")
    assert t_resp_closed.json()["status"] == "closed"


@pytest.mark.asyncio
async def test_skip_ticket(ticket_client: AsyncClient) -> None:
    """Test skipping a ticket."""
    resp = await ticket_client.post("/api/tickets/1/skip")
    assert resp.status_code == 200
    assert resp.json()["status"] == "skipped"


@pytest.mark.asyncio
async def test_calibration_endpoints(ticket_client: AsyncClient) -> None:
    """Test POST /api/calibrations and GET /api/calibrations/latest."""
    # Post calibration: broker price 2652.3, source price is 2651.0 -> offset +1.3
    resp = await ticket_client.post(
        "/api/calibrations",
        json={
            "symbol": "XAUUSD",
            "broker_profile": "Exness Standard",
            "broker_price": 2652.3,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "XAUUSD"
    assert data["offset"] == 1.3
    assert data["is_active"] is True

    # Retrieve latest
    get_resp = await ticket_client.get("/api/calibrations/latest?symbol=XAUUSD")
    assert get_resp.status_code == 200
    assert get_resp.json()["offset"] == 1.3


@pytest.mark.asyncio
async def test_paper_trading_endpoints(ticket_client: AsyncClient) -> None:
    """Test paper trade list, account metrics, and manual close."""
    # List trades
    list_resp = await ticket_client.get("/api/paper/trades")
    assert list_resp.status_code == 200
    trades = list_resp.json()
    assert len(trades) >= 1
    assert trades[0]["status"] == "OPEN"

    # Account metrics
    acc_resp = await ticket_client.get("/api/paper/account")
    assert acc_resp.status_code == 200
    acc = acc_resp.json()
    assert acc["initial_equity"] == 1000.0
    assert acc["open_positions_count"] == 1

    # Manually close paper trade 1 at 2660.0
    close_resp = await ticket_client.post(
        "/api/paper/trades/1/close",
        json={"exit_price": 2660.0},
    )
    assert close_resp.status_code == 200
    c_data = close_resp.json()
    assert c_data["status"] == "CLOSED"
    assert c_data["exit_price"] == 2660.0
    assert (c_data["pnl_usd"] or 0) > 0
