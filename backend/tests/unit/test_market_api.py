"""Integration tests for market data endpoints (/symbols, /candles)."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from traderadar.api.app import app
from traderadar.api.deps import get_db, get_redis_client
from traderadar.core.models import Base, Candle, User
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
async def market_client() -> AsyncGenerator[AsyncClient, None]:
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

    # Seed admin user and sample candles
    async with session_maker() as session:
        admin = User(
            id=1,
            email="admin@example.com",
            password_hash=hash_password("Password123!"),
            created_at=utc_now(),
        )
        session.add(admin)

        c1 = Candle(
            symbol="BTCUSDT",
            tf="M15",
            open_time=datetime(2026, 10, 15, 10, 0, tzinfo=UTC),
            open=81000.0,
            high=81200.0,
            low=80900.0,
            close=81150.0,
            volume=50.0,
            taker_buy_volume=25.0,
            source="binance_futures",
        )
        c2 = Candle(
            symbol="BTCUSDT",
            tf="M15",
            open_time=datetime(2026, 10, 15, 10, 15, tzinfo=UTC),
            open=81150.0,
            high=81300.0,
            low=81100.0,
            close=81280.0,
            volume=60.0,
            taker_buy_volume=35.0,
            source="binance_futures",
        )
        session.add_all([c1, c2])
        await session.commit()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            yield session

    async def override_get_redis() -> AsyncGenerator[FakeRedis, None]:
        yield fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis

    token = create_access_token(user_id=1, email="admin@example.com")
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"access_token": token},
    ) as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_symbols_unauthorized() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/symbols")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_symbols_authenticated(market_client: AsyncClient) -> None:
    res = await market_client.get("/api/symbols")
    assert res.status_code == 200
    data = res.json()
    assert "symbols" in data
    symbols = data["symbols"]
    assert len(symbols) >= 4
    symbols_map = {s["symbol"]: s for s in symbols}
    assert "BTCUSDT" in symbols_map
    assert "XAUUSD" in symbols_map
    gold = symbols_map["XAUUSD"]
    assert gold["asset"] == "gold"
    assert gold["gold_status"] is not None
    assert "is_open" in gold["gold_status"]


@pytest.mark.asyncio
async def test_get_candles(market_client: AsyncClient) -> None:
    res = await market_client.get("/api/candles", params={"symbol": "BTCUSDT", "tf": "M15"})
    assert res.status_code == 200
    candles = res.json()
    assert len(candles) == 2
    assert candles[0]["symbol"] == "BTCUSDT"
    assert candles[0]["tf"] == "M15"
    assert candles[0]["open"] == 81000.0
    assert candles[1]["close"] == 81280.0


@pytest.mark.asyncio
async def test_get_indicators_unauthorized() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/indicators", params={"symbol": "BTCUSDT", "tf": "M15"})
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_indicators_endpoint(market_client: AsyncClient) -> None:
    res = await market_client.get(
        "/api/indicators",
        params={"symbol": "BTCUSDT", "tf": "M15", "limit": 100},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "BTCUSDT"
    assert data["tf"] == "M15"
    assert "overlays" in data
    assert "panes" in data
    assert "latest_indicators" in data
    assert "calc_time_ms" in data
    assert isinstance(data["latest_indicators"], list)
