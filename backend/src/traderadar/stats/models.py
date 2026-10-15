"""Pydantic models and schemas for TradeRadar Journal and Statistics."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TradeRecordItem(BaseModel):
    """Normalized single trade item representation for journal."""

    id: int
    ticket_id: int | None = None
    signal_id: int | None = None
    analysis_id: int | None = None
    book: str = "paper"  # "paper" | "real"
    symbol: str
    strategy: str
    side: str
    entry_time: datetime
    entry_time_wib: str
    entry_price: float
    exit_time: datetime | None = None
    exit_time_wib: str | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    bars_held: int = 0
    pnl_usd: float = 0.0
    pnl_r: float = 0.0
    fees_usd: float = 0.0
    slippage_points: float = 0.0
    verdict: str = "NEUTRAL"
    session: str = "Asia"
    broker_profile: str | None = None
    is_virtual: bool = False
    notes: str | None = None


class JournalKPIs(BaseModel):
    """Core key performance indicators for a trading journal book."""

    total_trades: int = 0
    win_trades: int = 0
    loss_trades: int = 0
    be_trades: int = 0
    winrate_pct: float = 0.0
    profit_factor: float | None = None
    expectancy_r: float = 0.0
    avg_win_r: float = 0.0
    avg_loss_r: float = 0.0
    risk_reward_ratio: float = 0.0
    max_drawdown_r: float = 0.0
    max_drawdown_usd: float = 0.0
    max_win_streak: int = 0
    max_loss_streak: int = 0
    current_streak: int = 0
    total_pnl_usd: float = 0.0
    total_pnl_r: float = 0.0
    gross_profit_usd: float = 0.0
    gross_loss_usd: float = 0.0


class EquityPoint(BaseModel):
    """A data point on the cumulative equity curve."""

    trade_id: int
    time: str
    time_wib: str
    symbol: str
    side: str
    pnl_r: float
    pnl_usd: float
    cumulative_r: float
    cumulative_usd: float
    drawdown_r: float


class RDistributionBin(BaseModel):
    """Histogram bin for R return distribution."""

    range_label: str
    count: int
    percentage: float


class HeatmapCell(BaseModel):
    """Single cell in the Day of Week x Hour of Day (WIB) winrate heatmap."""

    day_of_week: int  # 0 = Senin, ..., 6 = Minggu
    day_name: str
    hour_wib: int  # 0..23
    total_trades: int = 0
    win_trades: int = 0
    winrate_pct: float = 0.0
    total_pnl_r: float = 0.0
    total_pnl_usd: float = 0.0


class BreakdownItem(BaseModel):
    """Breakdown metrics for a specific dimension (symbol, strategy, session, verdict)."""

    category: str
    total_trades: int = 0
    win_trades: int = 0
    loss_trades: int = 0
    winrate_pct: float = 0.0
    profit_factor: float | None = None
    expectancy_r: float = 0.0
    avg_win_r: float = 0.0
    avg_loss_r: float = 0.0
    total_pnl_usd: float = 0.0
    total_pnl_r: float = 0.0


class IndicatorAccuracyItem(BaseModel):
    """Akurasi per indikator: performa ketika indikator searah vs berlawanan arah sinyal."""

    name: str
    aligned_trades: int = 0
    aligned_wins: int = 0
    aligned_winrate_pct: float = 0.0
    aligned_avg_r: float = 0.0
    contrarian_trades: int = 0
    contrarian_wins: int = 0
    contrarian_winrate_pct: float = 0.0
    contrarian_avg_r: float = 0.0
    net_edge_pct: float = 0.0


class MacroFilterImpactItem(BaseModel):
    """Nilai macro filter: evaluasi sinyal terblokir vs simulasi virtual."""

    code: str
    name: str
    blocked_count: int = 0
    virtual_losses_prevented: int = 0
    virtual_wins_missed: int = 0
    net_r_saved: float = 0.0
    effectiveness: str = "Netral"  # "Positif (Melindungi Modal)" | "Netral" | "Perlu Evaluasi"


class BrokerSlippageItem(BaseModel):
    """Slippage breakdown per broker profile."""

    broker_profile: str
    total_executions: int
    avg_slippage_points: float
    total_slippage_cost_usd: float


class SymbolSlippageItem(BaseModel):
    """Slippage breakdown per symbol."""

    symbol: str
    total_executions: int
    avg_slippage_points: float
    total_slippage_cost_usd: float


class SlippageStats(BaseModel):
    """Real slippage metrics between planned ticket entry and actual execution fill."""

    total_executions: int = 0
    avg_slippage_points: float = 0.0
    median_slippage_points: float = 0.0
    min_slippage_points: float = 0.0
    max_slippage_points: float = 0.0
    total_slippage_cost_usd: float = 0.0
    by_broker: list[BrokerSlippageItem] = Field(default_factory=list)
    by_symbol: list[SymbolSlippageItem] = Field(default_factory=list)


class JournalResponse(BaseModel):
    """Full comprehensive journal response payload."""

    book: str  # "paper" | "real" | "compare"
    filter_range: str
    filter_symbol: str | None = None
    filter_strategy: str | None = None
    kpis: JournalKPIs
    compare_paper_kpis: JournalKPIs | None = None
    compare_real_kpis: JournalKPIs | None = None
    equity_curve: list[EquityPoint] = Field(default_factory=list)
    r_distribution: list[RDistributionBin] = Field(default_factory=list)
    heatmap: list[HeatmapCell] = Field(default_factory=list)
    breakdowns: dict[str, list[BreakdownItem]] = Field(default_factory=dict)
    indicator_accuracy: list[IndicatorAccuracyItem] = Field(default_factory=list)
    macro_filter_impact: list[MacroFilterImpactItem] = Field(default_factory=list)
    slippage_metrics: SlippageStats
    trades: list[TradeRecordItem] = Field(default_factory=list)


class TradeAnalysisSnapshotResponse(BaseModel):
    """Full snapshot of the technical analysis when the trade was initiated."""

    trade_id: int
    symbol: str
    tf: str
    bar_time: str
    score: float
    verdict: str
    indicators: list[dict[str, Any]]
    counts: dict[str, Any]
    category_votes: dict[str, Any]
    macro: dict[str, Any]
    htf: dict[str, Any]
    strategy_b: dict[str, Any]
    weights_version: str
