"""Integration tests for analysis endpoints.
(/analysis/{symbol}, /analysis/{symbol}/history, /signals).
"""

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
from traderadar.core.models import AnalysisRecord, Base, Candle, SignalRecord, User
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
async def analysis_client() -> AsyncGenerator[AsyncClient, None]:
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

    # Seed admin, sample candles, and sample analysis
    async with session_maker() as session:
        admin = User(
            id=1,
            email="admin@example.com",
            password_hash=hash_password("Password123!"),
            created_at=utc_now(),
        )
        session.add(admin)

        # Seed 30 M15 candles so on-the-fly analysis can also compute if needed
        for i in range(30):
            c_time = now - timedelta(minutes=15 * (30 - i))
            candle = Candle(
                symbol="BTCUSDT",
                tf="M15",
                open_time=c_time,
                open=65000.0 + i * 10,
                high=65050.0 + i * 10,
                low=64950.0 + i * 10,
                close=65020.0 + i * 10,
                volume=150.0,
                taker_buy_volume=80.0,
                source="binance_futures:BTCUSDT",
            )
            session.add(candle)

        # Seed an AnalysisRecord and a SignalRecord
        rec = AnalysisRecord(
            symbol="BTCUSDT",
            tf="M15",
            bar_time=now,
            source="binance_futures:BTCUSDT",
            score=62.5,
            verdict="STRONG_LONG",
            counts={"BULL": 6, "BEAR": 1, "NEUTRAL": 3, "NA": 0},
            indicators=[
                {
                    "key": "vwap",
                    "category": "order_flow",
                    "state": "BULL",
                    "strength": 0.8,
                    "values": {"vwap": 65000.0},
                    "reason": "Harga di atas VWAP",
                }
            ],
            category_votes={"trend": "BULL", "momentum": "BULL"},
            htf={"H1": "BULL", "H4": "BULL", "D1": "NEUTRAL"},
            macro={"passed": True, "checks": [], "blocked_by": []},
            strategy_b={"state": "LONG", "confirmed": True, "reason": "Crossover EMA"},
            weights_version="v1-default",
            created_at=now,
        )
        session.add(rec)
        await session.flush()

        sig = SignalRecord(
            analysis_id=rec.id,
            strategy="konfluensi10",
            symbol="BTCUSDT",
            tf="M15",
            side="LONG",
            verdict="STRONG_LONG",
            bar_time=now,
            status="ticketed",
            blocked_by=[],
            confirmed_by_b=True,
            created_at=now,
        )
        session.add(sig)

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
async def test_get_latest_analysis(analysis_client: AsyncClient) -> None:
    """GET /api/analysis/{symbol} should return current confluence analysis."""
    resp = await analysis_client.get("/api/analysis/BTCUSDT?tf=M15")
    assert resp.status_code == 200
    data = resp.json()

    assert data["symbol"] == "BTCUSDT"
    assert data["score"] == 62.5
    assert data["verdict"] == "STRONG_LONG"
    assert "indicators" in data
    assert "macro" in data
    assert "strategy_b" in data


@pytest.mark.asyncio
async def test_get_analysis_history(analysis_client: AsyncClient) -> None:
    """GET /api/analysis/{symbol}/history should return score history list."""
    resp = await analysis_client.get("/api/analysis/BTCUSDT/history?tf=M15&limit=10")
    assert resp.status_code == 200
    data = resp.json()

    assert data["symbol"] == "BTCUSDT"
    assert len(data["history"]) >= 1
    assert data["history"][0]["score"] == 62.5


@pytest.mark.asyncio
async def test_get_signals(analysis_client: AsyncClient) -> None:
    """GET /api/signals should return recorded signals."""
    resp = await analysis_client.get("/api/signals?symbol=BTCUSDT")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] >= 1
    sig = data["signals"][0]
    assert sig["symbol"] == "BTCUSDT"
    assert sig["side"] == "LONG"
    assert sig["status"] == "ticketed"
