"""Integration tests for Journal and Statistics API endpoints."""

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
    AnalysisRecord,
    Base,
    PaperTradeRecord,
    RealExecutionRecord,
    SignalRecord,
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
async def stats_client() -> AsyncGenerator[AsyncClient, None]:
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

        # 1. Seed Analysis
        analysis = AnalysisRecord(
            id=1,
            symbol="XAUUSDT",
            tf="M15",
            bar_time=now,
            source="binance_futures",
            score=8.5,
            verdict="STRONG_LONG",
            counts={"bullish": 8, "bearish": 1, "neutral": 1},
            indicators=[
                {"name": "Supertrend", "signal": "BULLISH", "value": 2640.0},
                {"name": "EMA (8/21/55)", "signal": "BULLISH", "value": 2645.0},
                {"name": "RSI (14)", "signal": "BEARISH", "value": 72.0},
            ],
            category_votes={"trend": 3.0, "momentum": 2.0},
            htf={"H1": "BULLISH", "H4": "BULLISH"},
            macro={"M1": True, "M2": True, "M3": True, "M4": True},
            strategy_b={"signal": "LONG", "confirmed": True},
            weights_version="v1.0",
        )
        session.add(analysis)

        # 2. Seed Signal
        signal = SignalRecord(
            id=1,
            analysis_id=1,
            strategy="Konfluensi-10",
            symbol="XAUUSDT",
            tf="M15",
            side="LONG",
            verdict="STRONG_LONG",
            bar_time=now,
            status="active",
        )
        session.add(signal)

        # 3. Seed Ticket
        ticket = TicketRecord(
            id=1,
            signal_id=1,
            symbol="XAUUSDT",
            side="LONG",
            strategy="Konfluensi-10",
            score=8.5,
            source="binance_futures",
            entry=2650.0,
            entry_low=2648.0,
            entry_high=2652.0,
            sl=2640.0,
            tp1=2665.0,
            tp2=2680.0,
            atr=5.0,
            sl_points=10.0,
            sl_atr_mult=2.0,
            tp1_points=15.0,
            tp2_points=30.0,
            invalidation="Break below 2640",
            valid_until=now + timedelta(hours=2),
            status="closed",
        )
        session.add(ticket)

        # 4. Seed Closed Paper Trade (Winning)
        paper_1 = PaperTradeRecord(
            id=1,
            ticket_id=1,
            signal_id=1,
            strategy="Konfluensi-10",
            symbol="XAUUSDT",
            side="LONG",
            entry_time=now,
            entry_price=2650.0,
            size=1.0,
            sl=2640.0,
            tp1=2665.0,
            tp2=2680.0,
            status="CLOSED",
            exit_time=now + timedelta(hours=1),
            exit_price=2665.0,
            exit_reason="TP1",
            pnl_usd=1500.0,
            pnl_r=1.5,
            fees_usd=5.0,
            is_virtual=False,
        )
        session.add(paper_1)

        # 5. Seed Closed Paper Trade (Losing)
        paper_2 = PaperTradeRecord(
            id=2,
            strategy="Konfluensi-10",
            symbol="BTCUSDT",
            side="SHORT",
            entry_time=now - timedelta(days=2),
            entry_price=68000.0,
            size=0.1,
            sl=69000.0,
            tp1=66500.0,
            tp2=65000.0,
            status="CLOSED",
            exit_time=now - timedelta(days=2, hours=-2),
            exit_price=69000.0,
            exit_reason="SL",
            pnl_usd=-100.0,
            pnl_r=-1.0,
            fees_usd=2.0,
            is_virtual=False,
        )
        session.add(paper_2)

        # 6. Seed Blocked Virtual Signal & Trade
        blocked_sig = SignalRecord(
            id=2,
            strategy="Konfluensi-10",
            symbol="XAUUSDT",
            tf="M15",
            side="LONG",
            verdict="STRONG_LONG",
            bar_time=now - timedelta(days=1),
            status="blocked",
            blocked_by=["M4", "M1"],
        )
        session.add(blocked_sig)

        virtual_pt = PaperTradeRecord(
            id=3,
            signal_id=2,
            strategy="Konfluensi-10",
            symbol="XAUUSDT",
            side="LONG",
            entry_time=now - timedelta(days=1),
            entry_price=2640.0,
            size=1.0,
            sl=2630.0,
            tp1=2655.0,
            tp2=2670.0,
            status="CLOSED",
            exit_time=now - timedelta(days=1, hours=-1),
            exit_price=2630.0,
            exit_reason="SL",
            pnl_usd=-1000.0,
            pnl_r=-1.0,
            fees_usd=0.0,
            is_virtual=True,
        )
        session.add(virtual_pt)

        # 7. Seed Real Execution
        real_exec = RealExecutionRecord(
            id=1,
            ticket_id=1,
            broker_profile="IC Markets",
            fill_price=2650.5,  # 0.5 points adverse slippage
            lot=0.1,
            fill_time=now,
            exit_price=2665.0,
            exit_time=now + timedelta(hours=1),
            pnl_usd=145.0,
            pnl_r=1.45,
            slippage_points=0.5,
            source="ui",
            notes="Executed with standard spread",
        )
        session.add(real_exec)

        await session.commit()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as s:
            yield s

    async def override_get_redis() -> Any:
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis

    token = create_access_token(user_id=1, email="admin@example.com")
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        client.cookies.set("access_token", token)
        client.cookies.set("traderadar_access", token)
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_stats_unauthenticated() -> None:
    """Unauthenticated requests must be rejected with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/stats")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_stats_paper(stats_client: AsyncClient) -> None:
    """Test retrieving stats for Paper book."""
    res = await stats_client.get("/api/stats?book=paper&range=all")
    assert res.status_code == 200
    data = res.json()

    assert data["book"] == "paper"
    kpi = data["kpis"]
    assert kpi["total_trades"] == 2
    assert kpi["win_trades"] == 1
    assert kpi["loss_trades"] == 1
    assert kpi["winrate_pct"] == 50.0
    assert kpi["total_pnl_usd"] == 1400.0  # 1500 - 100
    assert kpi["total_pnl_r"] == 0.5  # 1.5 - 1.0

    # Equity curve and distribution
    assert len(data["equity_curve"]) == 2
    assert len(data["r_distribution"]) == 7
    assert len(data["heatmap"]) == 7 * 24

    # Indicator accuracy
    assert len(data["indicator_accuracy"]) == 10
    supertrend = next(i for i in data["indicator_accuracy"] if "Supertrend" in i["name"])
    assert supertrend["aligned_trades"] == 1
    assert supertrend["aligned_wins"] == 1

    # Macro filter impact
    assert len(data["macro_filter_impact"]) == 8
    m4 = next(x for x in data["macro_filter_impact"] if x["code"] == "M4")
    assert m4["blocked_count"] == 1
    assert m4["virtual_losses_prevented"] == 1
    assert m4["net_r_saved"] == 1.0
    assert m4["effectiveness"] == "Positif (Melindungi Modal)"

    # Trades list
    assert len(data["trades"]) == 2
    assert data["trades"][0]["symbol"] in ("XAUUSDT", "BTCUSDT")


@pytest.mark.asyncio
async def test_get_stats_real(stats_client: AsyncClient) -> None:
    """Test retrieving stats for Real book."""
    res = await stats_client.get("/api/stats?book=real&range=all")
    assert res.status_code == 200
    data = res.json()

    assert data["book"] == "real"
    kpi = data["kpis"]
    assert kpi["total_trades"] == 1
    assert kpi["win_trades"] == 1
    assert kpi["winrate_pct"] == 100.0
    assert kpi["total_pnl_usd"] == 145.0

    # Slippage metrics
    slip = data["slippage_metrics"]
    assert slip["total_executions"] == 1
    assert slip["avg_slippage_points"] == 0.5
    assert len(slip["by_broker"]) == 1
    assert slip["by_broker"][0]["broker_profile"] == "IC Markets"


@pytest.mark.asyncio
async def test_get_stats_compare(stats_client: AsyncClient) -> None:
    """Test side-by-side comparison mode."""
    res = await stats_client.get("/api/stats?book=compare&range=all")
    assert res.status_code == 200
    data = res.json()

    assert data["book"] == "compare"
    assert data["compare_paper_kpis"] is not None
    assert data["compare_real_kpis"] is not None
    assert data["compare_paper_kpis"]["total_trades"] == 2
    assert data["compare_real_kpis"]["total_trades"] == 1


@pytest.mark.asyncio
async def test_get_stats_filter_symbol(stats_client: AsyncClient) -> None:
    """Test filtering stats by symbol."""
    res = await stats_client.get("/api/stats?book=paper&symbol=XAUUSDT")
    assert res.status_code == 200
    data = res.json()
    assert data["kpis"]["total_trades"] == 1
    assert data["trades"][0]["symbol"] == "XAUUSDT"


@pytest.mark.asyncio
async def test_export_journal_csv(stats_client: AsyncClient) -> None:
    """Test exporting CSV formatted journal."""
    res = await stats_client.get("/api/stats/export.csv?book=paper&range=all")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "attachment; filename=" in res.headers["content-disposition"]

    content = res.text
    # Should contain headers
    assert "ID,Buku,Simbol,Strategi" in content
    assert "XAUUSDT" in content
    assert "BTCUSDT" in content


@pytest.mark.asyncio
async def test_get_trade_snapshot(stats_client: AsyncClient) -> None:
    """Test retrieving technical confluence snapshot for a trade."""
    res = await stats_client.get("/api/stats/trades/1/snapshot?book=paper")
    assert res.status_code == 200
    data = res.json()
    assert data["trade_id"] == 1
    assert data["symbol"] == "XAUUSDT"
    assert data["score"] == 8.5
    assert data["verdict"] == "STRONG_LONG"
    assert len(data["indicators"]) == 3


@pytest.mark.asyncio
async def test_get_trade_snapshot_not_found(stats_client: AsyncClient) -> None:
    """Snapshot for unknown trade returns 404."""
    res = await stats_client.get("/api/stats/trades/999/snapshot?book=paper")
    assert res.status_code == 404
