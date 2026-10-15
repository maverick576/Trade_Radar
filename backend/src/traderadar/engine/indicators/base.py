"""Base types, data structures, and protocol for indicators."""

from typing import Literal

from pydantic import BaseModel, Field

IndicatorCategory = Literal[
    "trend",
    "momentum",
    "order_flow",
    "derivatives",
    "microstructure",
    "ml",
    "sentiment",
]

IndicatorState = Literal["BULL", "BEAR", "NEUTRAL", "NA"]


class IndicatorResult(BaseModel):
    """Standard output schema of an indicator evaluation."""

    key: str
    category: IndicatorCategory
    state: IndicatorState
    strength: float = Field(default=0.0, ge=0.0, le=1.0)
    values: dict[str, float] = Field(default_factory=dict)
    reason: str
    live_only: bool = False


class MarketContext(BaseModel):
    """Auxiliary context for non-candle indicators (derivatives, orderbook, sentiment)."""

    funding_rate: float | None = None
    open_interest_current: float | None = None
    open_interest_4h_ago: float | None = None
    orderbook_bids: list[tuple[float, float]] | None = None  # [(price, qty), ...]
    orderbook_asks: list[tuple[float, float]] | None = None
    smoothed_obi: float | None = None
    fear_and_greed: int | None = None
    long_short_ratio: float | None = None
    htf_trend: str | None = None  # e.g. "BULL" / "BEAR" from H1
    is_gold: bool = False
    model_auc: float | None = None
    model_predictions: tuple[float, float] | None = None  # (p_up, p_down)
