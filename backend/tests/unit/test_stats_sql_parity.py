"""Unit test for verifying exact parity between independent raw SQL and traderadar.stats."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from traderadar.core.models import (
    Base,
    PaperTradeRecord,
    RealExecutionRecord,
    TicketRecord,
)
from traderadar.scripts.verify_stats import verify_stats_parity


@pytest.mark.asyncio
async def test_independent_sql_parity_empty_db() -> None:
    """Parity check on empty database."""
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
        result = await verify_stats_parity(session)
        assert result["status"] == "PASSED"
        assert result["paper"]["total_trades"] == 0
        assert result["real"]["total_trades"] == 0

    await engine.dispose()


@pytest.mark.asyncio
async def test_independent_sql_parity_with_trades() -> None:
    """Parity check with seeded paper trades and real executions."""
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

    now = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)

    async with session_maker() as session:
        # Seed tickets
        t1 = TicketRecord(
            id=10,
            symbol="XAUUSDT",
            side="LONG",
            strategy="Konfluensi-10",
            score=8.0,
            source="binance_futures",
            entry=2650.0,
            entry_low=2648.0,
            entry_high=2652.0,
            sl=2635.0,
            tp1=2665.0,
            tp2=2680.0,
            atr=5.0,
            sl_points=15.0,
            sl_atr_mult=3.0,
            tp1_points=15.0,
            tp2_points=30.0,
            invalidation="Break 2635",
            valid_until=now + timedelta(hours=2),
            status="closed",
        )
        t2 = TicketRecord(
            id=20,
            symbol="BTCUSDT",
            side="SHORT",
            strategy="Triple-EMA",
            score=7.5,
            source="binance_futures",
            entry=68000.0,
            entry_low=67900.0,
            entry_high=68100.0,
            sl=68500.0,
            tp1=67000.0,
            tp2=66000.0,
            atr=250.0,
            sl_points=500.0,
            sl_atr_mult=2.0,
            tp1_points=1000.0,
            tp2_points=2000.0,
            invalidation="Break 68500",
            valid_until=now + timedelta(hours=2),
            status="closed",
        )
        session.add_all([t1, t2])

        # Seed closed paper trades
        p1 = PaperTradeRecord(
            id=101,
            ticket_id=10,
            strategy="Konfluensi-10",
            symbol="XAUUSDT",
            side="LONG",
            entry_time=now - timedelta(hours=3),
            entry_price=2650.0,
            size=1.0,
            sl=2635.0,
            tp1=2665.0,
            tp2=2680.0,
            status="CLOSED",
            exit_time=now - timedelta(hours=2),
            exit_price=2665.0,
            exit_reason="TP1",
            pnl_usd=1500.0,
            pnl_r=1.0,
            fees_usd=5.0,
            is_virtual=False,
        )
        p2 = PaperTradeRecord(
            id=102,
            ticket_id=20,
            strategy="Triple-EMA",
            symbol="BTCUSDT",
            side="SHORT",
            entry_time=now - timedelta(hours=2),
            entry_price=68000.0,
            size=0.1,
            sl=68500.0,
            tp1=67000.0,
            tp2=66000.0,
            status="CLOSED",
            exit_time=now - timedelta(hours=1),
            exit_price=68500.0,
            exit_reason="SL",
            pnl_usd=-50.0,
            pnl_r=-1.0,
            fees_usd=1.0,
            is_virtual=False,
        )
        p3 = PaperTradeRecord(
            id=103,
            strategy="Konfluensi-10",
            symbol="ETHUSDT",
            side="LONG",
            entry_time=now - timedelta(hours=1),
            entry_price=3500.0,
            size=2.0,
            sl=3450.0,
            tp1=3600.0,
            tp2=3700.0,
            status="CLOSED",
            exit_time=now,
            exit_price=3500.0,
            exit_reason="BE",
            pnl_usd=0.0,
            pnl_r=0.0,
            fees_usd=0.0,
            is_virtual=False,
        )
        session.add_all([p1, p2, p3])

        # Seed real executions
        r1 = RealExecutionRecord(
            id=201,
            ticket_id=10,
            broker_profile="IC Markets",
            fill_price=2650.3,
            lot=0.05,
            fill_time=now - timedelta(hours=3),
            exit_price=2665.0,
            exit_time=now - timedelta(hours=2),
            pnl_usd=73.5,
            pnl_r=0.98,
            slippage_points=0.3,
            source="ui",
        )
        r2 = RealExecutionRecord(
            id=202,
            ticket_id=20,
            broker_profile="Exness",
            fill_price=68010.0,
            lot=0.1,
            fill_time=now - timedelta(hours=2),
            exit_price=68500.0,
            exit_time=now - timedelta(hours=1),
            pnl_usd=-49.0,
            pnl_r=-0.98,
            slippage_points=10.0,
            source="telegram",
        )
        session.add_all([r1, r2])

        await session.commit()

        result = await verify_stats_parity(session)
        assert result["status"] == "PASSED"

        # Verify paper trade metrics parity
        assert result["paper"]["total_trades"] == 3
        assert round(result["paper"]["winrate_pct"], 1) == 33.3
        assert result["paper"]["total_pnl_usd"] == 1450.0
        assert result["paper"]["total_pnl_r"] == 0.0

        # Verify real execution metrics parity
        assert result["real"]["total_trades"] == 2
        assert result["real"]["winrate_pct"] == 50.0
        assert result["real"]["total_pnl_usd"] == 24.5
        assert result["real"]["total_pnl_r"] == 0.0
        assert result["real"]["avg_slippage"] == 5.15  # (0.3 + 10.0) / 2

    await engine.dispose()
