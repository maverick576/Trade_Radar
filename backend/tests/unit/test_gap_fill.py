"""Unit tests for candle gap detection and persistence."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from traderadar.core.models import Base
from traderadar.services.candle_store import get_candles, get_latest_candle, upsert_candles


@pytest.mark.asyncio
async def test_upsert_and_gap_fill_retrieval() -> None:
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

    async with session_maker() as session:
        # Initial batch with a gap: Bar 1 at 10:00, Bar 2 at 10:45 (missing 10:15 and 10:30)
        c1 = {
            "symbol": "BTCUSDT",
            "tf": "M15",
            "open_time": datetime(2026, 10, 15, 10, 0, tzinfo=UTC),
            "open": 81000.0,
            "high": 81200.0,
            "low": 80900.0,
            "close": 81150.0,
            "volume": 50.0,
            "taker_buy_volume": 25.0,
            "source": "binance_futures",
        }
        await upsert_candles(session, [c1])

        def to_utc(dt: datetime) -> datetime:
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)

        latest = await get_latest_candle(session, "BTCUSDT", "M15")
        assert latest is not None
        assert to_utc(latest.open_time) == datetime(2026, 10, 15, 10, 0, tzinfo=UTC)

        # Simulate gap filling missing bars
        gap_filled_bars = [
            {
                "symbol": "BTCUSDT",
                "tf": "M15",
                "open_time": datetime(2026, 10, 15, 10, 15, tzinfo=UTC),
                "open": 81150.0,
                "high": 81250.0,
                "low": 81100.0,
                "close": 81200.0,
                "volume": 40.0,
                "taker_buy_volume": 20.0,
                "source": "binance_futures",
            },
            {
                "symbol": "BTCUSDT",
                "tf": "M15",
                "open_time": datetime(2026, 10, 15, 10, 30, tzinfo=UTC),
                "open": 81200.0,
                "high": 81300.0,
                "low": 81180.0,
                "close": 81290.0,
                "volume": 45.0,
                "taker_buy_volume": 25.0,
                "source": "binance_futures",
            },
            {
                "symbol": "BTCUSDT",
                "tf": "M15",
                "open_time": datetime(2026, 10, 15, 10, 45, tzinfo=UTC),
                "open": 81290.0,
                "high": 81400.0,
                "low": 81250.0,
                "close": 81380.0,
                "volume": 55.0,
                "taker_buy_volume": 30.0,
                "source": "binance_futures",
            },
        ]
        inserted_count = await upsert_candles(session, gap_filled_bars)
        assert inserted_count == 3

        # Verify all 4 candles are retrieved chronologically
        all_candles = await get_candles(session, "BTCUSDT", "M15", limit=10)
        assert len(all_candles) == 4

        def to_utc(dt: datetime) -> datetime:
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)

        assert to_utc(all_candles[0].open_time) == datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
        assert to_utc(all_candles[1].open_time) == datetime(2026, 10, 15, 10, 15, tzinfo=UTC)
        assert to_utc(all_candles[2].open_time) == datetime(2026, 10, 15, 10, 30, tzinfo=UTC)
        assert to_utc(all_candles[3].open_time) == datetime(2026, 10, 15, 10, 45, tzinfo=UTC)

    await engine.dispose()
