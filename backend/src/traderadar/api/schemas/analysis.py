"""Pydantic schemas for Analysis and Signal API responses."""

from datetime import datetime

from pydantic import BaseModel

from traderadar.engine.indicators.base import IndicatorResult
from traderadar.engine.macro_filter import MacroFilterResult
from traderadar.engine.strategies.triple_ema import StrategyBResult


class AnalysisResponse(BaseModel):
    """Full confluence analysis response schema."""

    symbol: str
    tf: str
    bar_time: datetime
    source: str
    score: float
    verdict: str
    counts: dict[str, int]
    indicators: list[IndicatorResult]
    category_votes: dict[str, str]
    htf: dict[str, str]
    macro: MacroFilterResult
    strategy_b: StrategyBResult
    weights_version: str
    created_at: datetime


class ScoreHistoryItem(BaseModel):
    """Historical score data point for time-series chart."""

    bar_time: datetime
    score: float
    verdict: str


class ScoreHistoryResponse(BaseModel):
    """List of historical scores."""

    symbol: str
    tf: str
    history: list[ScoreHistoryItem]


class SignalItem(BaseModel):
    """Trading signal item schema."""

    id: int
    analysis_id: int | None = None
    strategy: str
    symbol: str
    tf: str
    side: str
    verdict: str
    bar_time: datetime
    status: str
    blocked_by: list[str] | None = None
    confirmed_by_b: bool = False
    created_at: datetime


class SignalsResponse(BaseModel):
    """Paginated signals list."""

    signals: list[SignalItem]
    total: int
