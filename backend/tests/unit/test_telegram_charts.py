"""Unit tests for Telegram Candlestick Chart PNG rendering."""

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from traderadar.core.models import Base, Candle
from traderadar.telegram.charts import (
    load_candles_and_render_chart,
    render_candlestick_chart,
)


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


def test_render_candlestick_chart_png_signature_and_performance() -> None:
    """Chart rendering generates valid PNG format and completes in < 1 second."""
    base_time = datetime(2026, 10, 15, 0, 0, tzinfo=UTC)
    candles: list[dict[str, Any]] = []

    price = 2650.0
    for i in range(40):
        t = base_time + timedelta(minutes=15 * i)
        c_open = price
        c_high = price + 2.5
        c_low = price - 1.8
        c_close = price + 1.2
        price = c_close
        candles.append(
            {
                "open_time": t,
                "open": c_open,
                "high": c_high,
                "low": c_low,
                "close": c_close,
                "volume": 250.0 + i * 5,
            }
        )

    levels = {
        "entry": 2651.0,
        "sl": 2636.5,
        "tp1": 2665.5,
        "tp2": 2680.0,
    }

    t0 = time.monotonic()
    png_bytes = render_candlestick_chart(candles=candles, symbol="XAUUSD", tf="M15", levels=levels)
    duration = time.monotonic() - t0

    # Verification: valid PNG header signature (89 50 4E 47 0D 0A 1A 0A)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    # File size should be substantial (typical chart 15KB - 80KB)
    assert len(png_bytes) > 10000
    # Must be fast (< 1.5s on any CPU)
    assert duration < 1.5


def test_render_candlestick_chart_empty_raises() -> None:
    """Empty candles list raises ValueError."""
    with pytest.raises(ValueError, match="Candles data cannot be empty"):
        render_candlestick_chart(candles=[], symbol="BTCUSDT", tf="M15")


@pytest.mark.asyncio
async def test_load_candles_and_render_chart_from_db(db_session: AsyncSession) -> None:
    """Load candles from database hypertable simulation and render chart PNG."""
    base_time = datetime(2026, 10, 15, 0, 0, tzinfo=UTC)

    # Insert 30 candles into db
    for i in range(30):
        c = Candle(
            symbol="XAUUSD",
            tf="M15",
            open_time=base_time + timedelta(minutes=15 * i),
            open=2650.0 + i * 0.2,
            high=2652.0 + i * 0.2,
            low=2649.0 + i * 0.2,
            close=2651.5 + i * 0.2,
            volume=500.0,
            source="binance_futures",
        )
        db_session.add(c)
    await db_session.commit()

    levels = {"entry": 2655.0, "sl": 2645.0, "tp1": 2665.0}
    chart_png = await load_candles_and_render_chart(
        session=db_session,
        symbol="XAUUSD",
        tf="M15",
        levels=levels,
        limit=30,
    )

    assert chart_png is not None
    assert chart_png.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(chart_png) > 10000
