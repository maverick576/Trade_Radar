"""Event schemas and stream/channel name definitions for Redis bus."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# Stream Names
STREAM_CANDLES_CLOSED = "candles.closed"
STREAM_SIGNALS = "signals"

# Pub/Sub Channels
CHANNEL_UI_EVENTS = "ui.events"
CHANNEL_TICKS_PREFIX = "ticks:"  # ticks:<symbol>

# Status Key Prefix
KEY_STATUS_PREFIX = "status:"  # status:<service>


class CandleClosedEvent(BaseModel):
    """Payload when a candlestick closes and is persisted."""

    event_id: str = Field(description="Unique idempotency id: {symbol}:{tf}:{bar_time}")
    symbol: str
    tf: str
    bar_time: datetime
    source: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    taker_buy_volume: float | None = None


class SignalEvent(BaseModel):
    """Payload published when a trading signal is generated."""

    event_id: str
    signal_id: int
    ticket_id: int | None = None
    strategy: str
    symbol: str
    tf: str
    side: Literal["LONG", "SHORT"]
    verdict: Literal["STRONG_LONG", "LONG", "NEUTRAL", "SHORT", "STRONG_SHORT"]
    bar_time: datetime
    created_at: datetime


class TickEvent(BaseModel):
    """Realtime tick published via pub/sub."""

    symbol: str
    price: float
    ts: datetime


class UIEvent(BaseModel):
    """Generic event routed to frontend WebSocket clients."""

    type: str
    data: dict[str, Any]
    ts: datetime


class ServiceHeartbeat(BaseModel):
    """Heartbeat metadata stored in Redis key status:<service>."""

    service: str
    version: str = "0.1.0"
    status: Literal["healthy", "degraded", "starting", "stopping"] = "healthy"
    ts: datetime
    uptime_seconds: float = 0.0
    details: dict[str, Any] = Field(default_factory=dict)
