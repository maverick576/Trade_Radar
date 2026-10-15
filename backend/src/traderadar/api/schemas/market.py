"""Pydantic schemas for market data endpoints (/symbols, /candles, /indicators)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from traderadar.engine.indicators.base import IndicatorResult


class CandleItem(BaseModel):
    """Candlestick bar representation."""

    symbol: str
    tf: str
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    taker_buy_volume: float | None = None
    source: str
    is_closed: bool = True


class SymbolItem(BaseModel):
    """Watchlist symbol metadata with capabilities, live price, and gold status."""

    symbol: str
    display: str
    asset: str  # "crypto" | "gold"
    active_source: str
    is_fallback: bool = False
    price: float | None = None
    change_24h: float | None = None
    high_24h: float | None = None
    low_24h: float | None = None
    capabilities: list[str] = Field(default_factory=list)
    gold_status: dict[str, Any] | None = None


class SymbolsResponse(BaseModel):
    """List of active symbols."""

    symbols: list[SymbolItem]


class IndicatorsResponse(BaseModel):
    """Response containing overlay timeseries, subpanes, and latest indicator verdict."""

    symbol: str
    tf: str
    overlays: dict[str, Any]
    panes: dict[str, Any]
    latest_indicators: list[IndicatorResult]
    calc_time_ms: float
