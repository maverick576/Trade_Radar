"""Unit tests for event schemas."""

from datetime import UTC, datetime

from traderadar.core.events import (
    CandleClosedEvent,
    ServiceHeartbeat,
    SignalEvent,
)


def test_candle_closed_event() -> None:
    now = datetime.now(UTC)
    event = CandleClosedEvent(
        event_id="BTCUSDT:M15:2026-10-15T00:00:00Z",
        symbol="BTCUSDT",
        tf="M15",
        bar_time=now,
        source="binance_futures:BTCUSDT",
        open=65000.0,
        high=65500.0,
        low=64800.0,
        close=65200.0,
        volume=120.5,
        taker_buy_volume=60.2,
    )
    assert event.symbol == "BTCUSDT"
    assert event.close == 65200.0


def test_signal_event() -> None:
    now = datetime.now(UTC)
    sig = SignalEvent(
        event_id="BTCUSDT:M15:2026-10-15T00:00:00Z",
        signal_id=1,
        ticket_id=10,
        strategy="konfluensi10",
        symbol="BTCUSDT",
        tf="M15",
        side="LONG",
        verdict="STRONG_LONG",
        bar_time=now,
        created_at=now,
    )
    assert sig.verdict == "STRONG_LONG"
    assert sig.side == "LONG"


def test_service_heartbeat() -> None:
    now = datetime.now(UTC)
    hb = ServiceHeartbeat(
        service="ingestor",
        version="0.1.0",
        status="healthy",
        ts=now,
        uptime_seconds=12.5,
    )
    assert hb.status == "healthy"
    assert hb.uptime_seconds == 12.5
