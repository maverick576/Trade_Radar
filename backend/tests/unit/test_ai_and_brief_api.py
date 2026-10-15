"""API integration tests for AI commentary and Market Brief endpoints."""

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
from traderadar.core.models import (
    AnalysisRecord,
    Base,
    Candle,
    TicketRecord,
    User,
)
from traderadar.core.security import create_access_token, hash_password
from traderadar.core.time import utc_now


class FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, Any] = {}

    async def get(self, key: str) -> str | None:
        val = self.storage.get(key)
        return str(val) if val is not None else None

    async def set(self, key: str, val: Any, *args: Any, **kwargs: Any) -> bool:
        self.storage[key] = str(val)
        return True

    def pipeline(self) -> "FakeRedisPipeline":
        return FakeRedisPipeline(self)


class FakeRedisPipeline:
    def __init__(self, parent: FakeRedis) -> None:
        self.parent = parent
        self.cmds: list[tuple[str, str]] = []

    def get(self, key: str) -> "FakeRedisPipeline":
        self.cmds.append(("get", key))
        return self

    def incr(self, key: str) -> "FakeRedisPipeline":
        self.cmds.append(("incr", key))
        return self

    def expire(self, key: str, sec: int) -> "FakeRedisPipeline":
        self.cmds.append(("expire", key))
        return self

    async def execute(self) -> list[Any]:
        res: list[Any] = []
        for cmd, key in self.cmds:
            if cmd == "get":
                res.append(self.parent.storage.get(key))
            elif cmd == "incr":
                v = int(self.parent.storage.get(key, 0)) + 1
                self.parent.storage[key] = v
                res.append(v)
            elif cmd == "expire":
                res.append(True)
        return res


@pytest_asyncio.fixture
async def ai_client() -> AsyncGenerator[AsyncClient, None]:
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

        # Seed Candle
        c = Candle(
            symbol="XAUUSDT",
            tf="M15",
            open_time=now,
            open=2650.0,
            high=2655.0,
            low=2648.0,
            close=2651.0,
            volume=100.0,
            taker_buy_volume=60.0,
            source="binance_futures:XAUUSDT",
        )
        session.add(c)

        # Seed AnalysisRecord
        a = AnalysisRecord(
            symbol="XAUUSDT",
            tf="M15",
            bar_time=now,
            source="binance_futures:XAUUSDT",
            score=65.0,
            verdict="STRONG_LONG",
            counts={"BULL": 6, "NEUTRAL": 3, "BEAR": 1, "NA": 0},
            indicators=[
                {
                    "key": "vwap",
                    "state": "BULL",
                    "values": {"vwap": 2640.0, "z": 0.8},
                    "reason": "Di atas VWAP",
                },
                {
                    "key": "supertrend",
                    "state": "BULL",
                    "values": {"supertrend": 2635.0},
                    "reason": "Hijau",
                },
            ],
            category_votes={"order_flow": "BULL", "trend": "BULL"},
            htf={"h1": "BULL", "h4": "BULL", "d1": "NEUTRAL"},
            macro={"passed": True, "checks": []},
            strategy_b={"state": "LONG"},
            weights_version="v1-default",
            created_at=utc_now(),
        )
        session.add(a)

        # Seed TicketRecord
        t = TicketRecord(
            symbol="XAUUSDT",
            side="LONG",
            strategy="Konfluensi-10",
            score=65.0,
            source="binance_futures:XAUUSDT",
            entry=2651.0,
            entry_low=2650.0,
            entry_high=2652.0,
            sl=2636.5,
            tp1=2665.5,
            tp2=2680.0,
            atr=9.7,
            sl_points=14.5,
            sl_atr_mult=1.5,
            tp1_points=14.5,
            tp2_points=29.0,
            invalidation="Supertrend M15 tembus",
            reasons=["VWAP bull"],
            risks=["Koreksi"],
            valid_until=now,
            status="new",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(t)
        await session.commit()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as s:
            yield s

    async def override_get_redis() -> Any:
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis

    token = create_access_token(user_id=1, email="admin@example.com")
    cookies = {"access_token": token}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_post_ai_comment_generates_comment(ai_client: AsyncClient) -> None:
    """POST /api/analysis/{symbol}/ai generates and persists AI commentary."""
    resp = await ai_client.post("/api/analysis/XAUUSDT/ai?tf=M15")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["symbol"] == "XAUUSDT"
    assert data["tf"] == "M15"
    assert "comment" in data
    assert data["comment"]["bias"] == "bullish"
    assert data["comment"]["setuju_dengan_engine"] is True
    assert len(data["comment"]["alasan_utama"]) >= 2
    assert data["valid"] is True


@pytest.mark.asyncio
async def test_get_ai_comment_returns_cached(ai_client: AsyncClient) -> None:
    """GET /api/analysis/{symbol}/ai retrieves the comment generated in previous test."""
    # First generate
    await ai_client.post("/api/analysis/XAUUSDT/ai?tf=M15")

    # Then retrieve
    resp = await ai_client.get("/api/analysis/XAUUSDT/ai?tf=M15")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["symbol"] == "XAUUSDT"
    assert data["comment"]["bias"] == "bullish"


@pytest.mark.asyncio
async def test_ai_quota_endpoint(ai_client: AsyncClient) -> None:
    """GET /api/ai/quota returns quota usage and limits."""
    resp = await ai_client.get("/api/ai/quota")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "rpm_used" in data
    assert "rpm_limit" in data
    assert "rpd_limit" in data
    assert "provider" in data


@pytest.mark.asyncio
async def test_briefs_endpoint(ai_client: AsyncClient) -> None:
    """POST and GET /api/briefs generates and returns Market Brief."""
    resp_post = await ai_client.post("/api/briefs?kind=morning")
    assert resp_post.status_code == 200, resp_post.text
    brief_data = resp_post.json()

    assert brief_data["kind"] == "morning"
    assert "narrative" in brief_data
    assert "ringkasan_umum" in brief_data["narrative"]
    assert "symbols" in brief_data["narrative"]

    resp_get = await ai_client.get("/api/briefs/latest")
    assert resp_get.status_code == 200, resp_get.text
    latest_data = resp_get.json()
    assert latest_data["id"] == brief_data["id"]
    assert latest_data["kind"] == "morning"
