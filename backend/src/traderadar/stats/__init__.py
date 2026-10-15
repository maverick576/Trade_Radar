"""TradeRadar Journal & Statistics package."""

from traderadar.stats.metrics import (
    build_equity_curve,
    calculate_breakdowns,
    calculate_heatmap,
    calculate_indicator_accuracy,
    calculate_kpis,
    calculate_macro_filter_impact,
    calculate_r_distribution,
    calculate_slippage_stats,
    get_trading_session_name,
)
from traderadar.stats.models import (
    BreakdownItem,
    EquityPoint,
    HeatmapCell,
    IndicatorAccuracyItem,
    JournalKPIs,
    JournalResponse,
    MacroFilterImpactItem,
    RDistributionBin,
    SlippageStats,
    TradeAnalysisSnapshotResponse,
    TradeRecordItem,
)
from traderadar.stats.service import (
    export_journal_csv,
    get_journal_stats,
    get_trade_analysis_snapshot,
)

__all__ = [
    "JournalKPIs",
    "TradeRecordItem",
    "EquityPoint",
    "RDistributionBin",
    "HeatmapCell",
    "BreakdownItem",
    "IndicatorAccuracyItem",
    "MacroFilterImpactItem",
    "SlippageStats",
    "JournalResponse",
    "TradeAnalysisSnapshotResponse",
    "calculate_kpis",
    "build_equity_curve",
    "calculate_r_distribution",
    "calculate_heatmap",
    "calculate_breakdowns",
    "calculate_indicator_accuracy",
    "calculate_macro_filter_impact",
    "calculate_slippage_stats",
    "get_trading_session_name",
    "get_journal_stats",
    "export_journal_csv",
    "get_trade_analysis_snapshot",
]
