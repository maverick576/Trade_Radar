"""Unit tests for pure math calculations in traderadar.stats.metrics."""

from datetime import UTC, datetime

from traderadar.stats.metrics import (
    build_equity_curve,
    calculate_breakdowns,
    calculate_heatmap,
    calculate_indicator_accuracy,
    calculate_kpis,
    calculate_macro_filter_impact,
    calculate_r_distribution,
    get_trading_session_name,
)
from traderadar.stats.models import TradeRecordItem


def _make_trade(
    id: int,
    pnl_r: float,
    pnl_usd: float,
    side: str = "LONG",
    symbol: str = "XAUUSDT",
    strategy: str = "Konfluensi-10",
    hour: int = 10,
    day_wib: int = 15,
) -> TradeRecordItem:
    # 2026-10-15 is Thursday (weekday index 3)
    dt = datetime(2026, 10, day_wib, hour, 0, tzinfo=UTC)
    return TradeRecordItem(
        id=id,
        book="paper",
        symbol=symbol,
        strategy=strategy,
        side=side,
        entry_time=dt,
        entry_time_wib=dt.isoformat(),
        entry_price=2650.0,
        exit_time=dt,
        exit_time_wib=dt.isoformat(),
        exit_price=2660.0 if pnl_r > 0 else 2640.0,
        exit_reason="TP1" if pnl_r > 0 else "SL",
        bars_held=4,
        pnl_usd=pnl_usd,
        pnl_r=pnl_r,
        fees_usd=1.5,
        slippage_points=0.1,
        verdict="STRONG_LONG",
        session=get_trading_session_name(dt),
        broker_profile="Test Broker",
        is_virtual=False,
    )


def test_calculate_kpis_empty() -> None:
    """Empty list returns zeroed KPIs."""
    kpi = calculate_kpis([])
    assert kpi.total_trades == 0
    assert kpi.winrate_pct == 0.0
    assert kpi.profit_factor is None
    assert kpi.expectancy_r == 0.0


def test_calculate_kpis_normal() -> None:
    """Normal distribution of winning, losing, and BE trades."""
    trades = [
        _make_trade(1, 1.5, 150.0),
        _make_trade(2, 2.0, 200.0),
        _make_trade(3, -1.0, -100.0),
        _make_trade(4, -1.0, -100.0),
        _make_trade(5, 0.0, 0.0),
    ]

    kpi = calculate_kpis(trades)
    assert kpi.total_trades == 5
    assert kpi.win_trades == 2
    assert kpi.loss_trades == 2
    assert kpi.be_trades == 1
    assert kpi.winrate_pct == 40.0  # 2 / 5
    assert kpi.total_pnl_usd == 150.0
    assert kpi.total_pnl_r == 1.5
    assert kpi.gross_profit_usd == 350.0
    assert kpi.gross_loss_usd == 200.0
    assert kpi.profit_factor == 1.75  # 350 / 200
    assert kpi.expectancy_r == 0.3  # 1.5 / 5
    assert kpi.avg_win_r == 1.75  # (1.5 + 2.0) / 2
    assert kpi.avg_loss_r == -1.0  # (-1.0 + -1.0) / 2
    assert kpi.risk_reward_ratio == 1.75
    assert kpi.max_win_streak == 2
    assert kpi.max_loss_streak == 2


def test_calculate_kpis_all_wins() -> None:
    """100% winrate handling."""
    trades = [
        _make_trade(1, 1.0, 100.0),
        _make_trade(2, 2.0, 200.0),
    ]
    kpi = calculate_kpis(trades)
    assert kpi.winrate_pct == 100.0
    assert kpi.gross_loss_usd == 0.0
    assert kpi.profit_factor == 300.0  # capped/represented as gross profit


def test_calculate_kpis_all_losses() -> None:
    """0% winrate handling."""
    trades = [
        _make_trade(1, -1.0, -100.0),
        _make_trade(2, -1.0, -100.0),
    ]
    kpi = calculate_kpis(trades)
    assert kpi.winrate_pct == 0.0
    assert kpi.profit_factor == 0.0
    assert kpi.avg_win_r == 0.0
    assert kpi.avg_loss_r == -1.0


def test_drawdown_calculation() -> None:
    """Max drawdown in R and USD."""
    trades = [
        _make_trade(1, 2.0, 200.0),   # cum: +2.0 R, peak: +2.0
        _make_trade(2, -1.5, -150.0), # cum: +0.5 R, dd: 1.5
        _make_trade(3, -1.0, -100.0), # cum: -0.5 R, dd: 2.5
        _make_trade(4, 3.0, 300.0),   # cum: +2.5 R, peak: +2.5
        _make_trade(5, -0.5, -50.0),  # cum: +2.0 R, dd: 0.5
    ]
    kpi = calculate_kpis(trades)
    assert kpi.max_drawdown_r == 2.5
    assert kpi.max_drawdown_usd == 250.0


def test_build_equity_curve() -> None:
    """Verify equity curve points calculation."""
    trades = [
        _make_trade(1, 1.0, 100.0),
        _make_trade(2, -0.5, -50.0),
    ]
    curve = build_equity_curve(trades)
    assert len(curve) == 2
    assert curve[0].cumulative_r == 1.0
    assert curve[0].cumulative_usd == 100.0
    assert curve[0].drawdown_r == 0.0
    assert curve[1].cumulative_r == 0.5
    assert curve[1].cumulative_usd == 50.0
    assert curve[1].drawdown_r == 0.5


def test_r_distribution() -> None:
    """Verify R return distribution bins."""
    trades = [
        _make_trade(1, -2.5, -250.0),  # <-2.0R
        _make_trade(2, -1.5, -150.0),  # [-2.0R, -1.0R)
        _make_trade(3, -0.5, -50.0),   # [-1.0R, 0.0R)
        _make_trade(4, 0.2, 20.0),     # [0.0R, 0.5R)
        _make_trade(5, 0.8, 80.0),     # [0.5R, 1.0R)
        _make_trade(6, 1.5, 150.0),    # [1.0R, 2.0R)
        _make_trade(7, 2.5, 250.0),    # >=2.0R
    ]
    bins = calculate_r_distribution(trades)
    assert len(bins) == 7
    for b in bins:
        assert b.count == 1
        assert round(b.percentage, 1) == 14.3


def test_calculate_heatmap() -> None:
    """Verify 7x24 heatmap cell generation and trade attribution."""
    trades = [
        _make_trade(1, 1.0, 100.0, hour=3, day_wib=15),
        _make_trade(2, -1.0, -100.0, hour=3, day_wib=15),
    ]
    heatmap = calculate_heatmap(trades)
    assert len(heatmap) == 7 * 24

    # Find the cell matching 2026-10-15 (Thursday) 10:00 WIB (which is 03:00 UTC)
    # Thursday is weekday index 3 (Senin=0, Selasa=1, Rabu=2, Kamis=3)
    matching = [c for c in heatmap if c.total_trades > 0]
    assert len(matching) == 1
    assert matching[0].total_trades == 2
    assert matching[0].win_trades == 1
    assert matching[0].winrate_pct == 50.0


def test_calculate_breakdowns() -> None:
    """Verify breakdowns by symbol, strategy, session, and verdict."""
    trades = [
        _make_trade(1, 1.0, 100.0, symbol="XAUUSDT", strategy="Konfluensi-10"),
        _make_trade(2, -1.0, -100.0, symbol="BTCUSDT", strategy="Triple-EMA"),
    ]
    bd = calculate_breakdowns(trades)
    assert "by_symbol" in bd
    assert "by_strategy" in bd
    assert "by_session" in bd
    assert "by_verdict" in bd

    symbols = {item.category for item in bd["by_symbol"]}
    assert "XAUUSDT" in symbols
    assert "BTCUSDT" in symbols


def test_indicator_accuracy() -> None:
    """Verify indicator accuracy for aligned vs contrarian signals."""
    trade_long_win = _make_trade(1, 1.5, 150.0, side="LONG")
    trade_long_loss = _make_trade(2, -1.0, -100.0, side="LONG")

    indicators_1 = [
        {"name": "Supertrend", "signal": "BULLISH"},  # Aligned with LONG, Won
        {"name": "RSI (14)", "signal": "BEARISH"},    # Contrarian with LONG, Won
    ]
    indicators_2 = [
        {"name": "Supertrend", "signal": "BEARISH"},  # Contrarian with LONG, Lost
        {"name": "RSI (14)", "signal": "BULLISH"},    # Aligned with LONG, Lost
    ]

    items = calculate_indicator_accuracy([
        (trade_long_win, indicators_1),
        (trade_long_loss, indicators_2),
    ])

    supertrend_stat = next(i for i in items if "Supertrend" in i.name)
    assert supertrend_stat.aligned_trades == 1
    assert supertrend_stat.aligned_wins == 1
    assert supertrend_stat.aligned_winrate_pct == 100.0
    assert supertrend_stat.contrarian_trades == 1
    assert supertrend_stat.contrarian_wins == 0
    assert supertrend_stat.contrarian_winrate_pct == 0.0
    assert supertrend_stat.net_edge_pct == 100.0


def test_macro_filter_impact() -> None:
    """Verify macro filter evaluation on blocked signals."""
    blocked_items = [
        {"blocked_by": ["M1", "M4"], "virtual_pnl_r": -1.0},  # Saved loss
        {"blocked_by": ["M1"], "virtual_pnl_r": 1.5},         # Missed win
    ]
    impact = calculate_macro_filter_impact(blocked_items)
    assert len(impact) == 8

    m1 = next(x for x in impact if x.code == "M1")
    assert m1.blocked_count == 2
    assert m1.virtual_losses_prevented == 1
    assert m1.virtual_wins_missed == 1
    # net saved: 1.0 - 1.5 = -0.5
    assert m1.net_r_saved == -0.5
    assert m1.effectiveness == "Perlu Evaluasi"

    m4 = next(x for x in impact if x.code == "M4")
    assert m4.blocked_count == 1
    assert m4.virtual_losses_prevented == 1
    assert m4.virtual_wins_missed == 0
    assert m4.net_r_saved == 1.0
    assert m4.effectiveness == "Positif (Melindungi Modal)"
