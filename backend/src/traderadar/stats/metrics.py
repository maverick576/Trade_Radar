"""Pure mathematical calculations and data aggregation for trading statistics."""

import statistics
from datetime import datetime
from typing import Any

from traderadar.core.models import RealExecutionRecord, TicketRecord
from traderadar.core.time import to_wib
from traderadar.stats.models import (
    BreakdownItem,
    BrokerSlippageItem,
    EquityPoint,
    HeatmapCell,
    IndicatorAccuracyItem,
    JournalKPIs,
    MacroFilterImpactItem,
    RDistributionBin,
    SlippageStats,
    SymbolSlippageItem,
    TradeRecordItem,
)

DAYS_INDONESIAN = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

STANDARD_INDICATOR_NAMES = [
    "EMA (8/21/55)",
    "VWAP",
    "Supertrend",
    "RSI (14)",
    "MACD",
    "Stochastic RSI",
    "Bollinger Bands",
    "ADX",
    "Volume & CVD",
    "Order Book Imbalance (OBI)",
]

MACRO_FILTER_DEFINITIONS = [
    ("M1", "M1: Spread Melebar"),
    ("M2", "M2: Berita High-Impact"),
    ("M3", "M3: HTF Alignment"),
    ("M4", "M4: Sesi Pasar Gold"),
    ("M5", "M5: Volatilitas Ekstrem"),
    ("M6", "M6: Volume Rendah"),
    ("M7", "M7: Funding Rate"),
    ("M8", "M8: Fear & Greed"),
]


def get_trading_session_name(dt: datetime) -> str:
    """Classify datetime into recognized global market trading sessions (in WIB)."""
    wib = to_wib(dt)
    hour = wib.hour
    if 7 <= hour < 14:
        return "Asia"
    elif 14 <= hour < 19:
        return "London"
    elif 19 <= hour < 23:
        return "London/NY Overlap"
    elif hour >= 23 or hour < 4:
        return "New York"
    else:
        return "Pacific"


def calculate_kpis(trades: list[TradeRecordItem]) -> JournalKPIs:
    """Compute core trading performance KPIs from a list of closed trades."""
    if not trades:
        return JournalKPIs()

    total = len(trades)
    wins = [t for t in trades if t.pnl_r > 0]
    losses = [t for t in trades if t.pnl_r < 0]
    be = [t for t in trades if t.pnl_r == 0]

    win_count = len(wins)
    loss_count = len(losses)
    be_count = len(be)
    winrate_pct = round((win_count / total) * 100.0, 2)

    gross_profit = sum(t.pnl_usd for t in wins if t.pnl_usd > 0)
    gross_loss = sum(abs(t.pnl_usd) for t in losses if t.pnl_usd < 0)

    if gross_loss > 0:
        profit_factor = round(gross_profit / gross_loss, 2)
    elif gross_profit > 0:
        profit_factor = round(gross_profit, 2)
    else:
        profit_factor = 0.0

    total_pnl_usd = round(sum(t.pnl_usd for t in trades), 2)
    total_pnl_r = round(sum(t.pnl_r for t in trades), 4)

    expectancy_r = round(total_pnl_r / total, 4) if total > 0 else 0.0
    avg_win_r = round(sum(t.pnl_r for t in wins) / win_count, 4) if win_count > 0 else 0.0
    avg_loss_r = round(sum(t.pnl_r for t in losses) / loss_count, 4) if loss_count > 0 else 0.0
    rrr = round(abs(avg_win_r / avg_loss_r), 2) if avg_loss_r != 0 else 0.0

    # Drawdowns and streaks calculated chronologically by exit time (or entry time)
    sorted_trades = sorted(trades, key=lambda t: t.exit_time or t.entry_time)

    cum_r = 0.0
    peak_r = 0.0
    max_dd_r = 0.0

    cum_usd = 0.0
    peak_usd = 0.0
    max_dd_usd = 0.0

    max_win_streak = 0
    max_loss_streak = 0
    curr_win = 0
    curr_loss = 0
    current_streak = 0

    for t in sorted_trades:
        cum_r += t.pnl_r
        if cum_r > peak_r:
            peak_r = cum_r
        dd_r = peak_r - cum_r
        if dd_r > max_dd_r:
            max_dd_r = dd_r

        cum_usd += t.pnl_usd
        if cum_usd > peak_usd:
            peak_usd = cum_usd
        dd_usd = peak_usd - cum_usd
        if dd_usd > max_dd_usd:
            max_dd_usd = dd_usd

        # Streak
        if t.pnl_r > 0:
            curr_win += 1
            curr_loss = 0
            current_streak = curr_win
            if curr_win > max_win_streak:
                max_win_streak = curr_win
        elif t.pnl_r < 0:
            curr_loss += 1
            curr_win = 0
            current_streak = -curr_loss
            if curr_loss > max_loss_streak:
                max_loss_streak = curr_loss
        else:
            curr_win = 0
            curr_loss = 0
            current_streak = 0

    return JournalKPIs(
        total_trades=total,
        win_trades=win_count,
        loss_trades=loss_count,
        be_trades=be_count,
        winrate_pct=winrate_pct,
        profit_factor=profit_factor,
        expectancy_r=expectancy_r,
        avg_win_r=avg_win_r,
        avg_loss_r=avg_loss_r,
        risk_reward_ratio=rrr,
        max_drawdown_r=round(max_dd_r, 4),
        max_drawdown_usd=round(max_dd_usd, 2),
        max_win_streak=max_win_streak,
        max_loss_streak=max_loss_streak,
        current_streak=current_streak,
        total_pnl_usd=total_pnl_usd,
        total_pnl_r=total_pnl_r,
        gross_profit_usd=round(gross_profit, 2),
        gross_loss_usd=round(gross_loss, 2),
    )


def build_equity_curve(trades: list[TradeRecordItem]) -> list[EquityPoint]:
    """Generate chronological equity curve data points."""
    if not trades:
        return []

    sorted_trades = sorted(trades, key=lambda t: t.exit_time or t.entry_time)

    curve: list[EquityPoint] = []
    cum_r = 0.0
    cum_usd = 0.0
    peak_r = 0.0

    for t in sorted_trades:
        cum_r += t.pnl_r
        cum_usd += t.pnl_usd
        if cum_r > peak_r:
            peak_r = cum_r
        dd_r = peak_r - cum_r

        ts = t.exit_time or t.entry_time
        ts_wib = t.exit_time_wib or t.entry_time_wib

        curve.append(
            EquityPoint(
                trade_id=t.id,
                time=ts.isoformat(),
                time_wib=ts_wib,
                symbol=t.symbol,
                side=t.side,
                pnl_r=round(t.pnl_r, 4),
                pnl_usd=round(t.pnl_usd, 2),
                cumulative_r=round(cum_r, 4),
                cumulative_usd=round(cum_usd, 2),
                drawdown_r=round(dd_r, 4),
            )
        )

    return curve


def calculate_r_distribution(trades: list[TradeRecordItem]) -> list[RDistributionBin]:
    """Calculate R return histogram bins."""
    from collections.abc import Callable

    bins: list[tuple[str, Callable[[float], bool]]] = [
        ("<-2.0R", lambda r: r < -2.0),
        ("[-2.0R, -1.0R)", lambda r: -2.0 <= r < -1.0),
        ("[-1.0R, 0.0R)", lambda r: -1.0 <= r < 0.0),
        ("[0.0R, 0.5R)", lambda r: 0.0 <= r < 0.5),
        ("[0.5R, 1.0R)", lambda r: 0.5 <= r < 1.0),
        ("[1.0R, 2.0R)", lambda r: 1.0 <= r < 2.0),
        (">=2.0R", lambda r: r >= 2.0),
    ]

    total = len(trades)
    result: list[RDistributionBin] = []

    for label, predicate in bins:
        count = sum(1 for t in trades if predicate(t.pnl_r))
        pct = round((count / total * 100.0), 2) if total > 0 else 0.0
        result.append(RDistributionBin(range_label=label, count=count, percentage=pct))

    return result


def calculate_heatmap(trades: list[TradeRecordItem]) -> list[HeatmapCell]:
    """Generate 7x24 heatmap grid for day of week x hour of day in WIB."""
    grid: dict[tuple[int, int], list[TradeRecordItem]] = {}
    for d in range(7):
        for h in range(24):
            grid[(d, h)] = []

    for t in trades:
        wib = to_wib(t.entry_time)
        day = wib.weekday()  # 0=Monday (Senin), ..., 6=Sunday (Minggu)
        hour = wib.hour
        grid[(day, hour)].append(t)

    cells: list[HeatmapCell] = []
    for d in range(7):
        day_name = DAYS_INDONESIAN[d]
        for h in range(24):
            sub = grid[(d, h)]
            total = len(sub)
            wins = sum(1 for t in sub if t.pnl_r > 0)
            wr = round((wins / total * 100.0), 2) if total > 0 else 0.0
            sum_r = round(sum(t.pnl_r for t in sub), 4)
            sum_usd = round(sum(t.pnl_usd for t in sub), 2)

            cells.append(
                HeatmapCell(
                    day_of_week=d,
                    day_name=day_name,
                    hour_wib=h,
                    total_trades=total,
                    win_trades=wins,
                    winrate_pct=wr,
                    total_pnl_r=sum_r,
                    total_pnl_usd=sum_usd,
                )
            )

    return cells


def _compute_single_breakdown(name: str, sub_trades: list[TradeRecordItem]) -> BreakdownItem:
    """Helper to compute BreakdownItem for a grouped subset of trades."""
    total = len(sub_trades)
    if total == 0:
        return BreakdownItem(category=name)

    wins = [t for t in sub_trades if t.pnl_r > 0]
    losses = [t for t in sub_trades if t.pnl_r < 0]

    win_count = len(wins)
    loss_count = len(losses)
    wr = round((win_count / total * 100.0), 2)

    gp = sum(t.pnl_usd for t in wins if t.pnl_usd > 0)
    gl = sum(abs(t.pnl_usd) for t in losses if t.pnl_usd < 0)
    pf = round(gp / gl, 2) if gl > 0 else (round(gp, 2) if gp > 0 else 0.0)

    tot_r = round(sum(t.pnl_r for t in sub_trades), 4)
    tot_usd = round(sum(t.pnl_usd for t in sub_trades), 2)

    exp_r = round(tot_r / total, 4)
    avg_win_r = round(sum(t.pnl_r for t in wins) / win_count, 4) if win_count > 0 else 0.0
    avg_loss_r = round(sum(t.pnl_r for t in losses) / loss_count, 4) if loss_count > 0 else 0.0

    return BreakdownItem(
        category=name,
        total_trades=total,
        win_trades=win_count,
        loss_trades=loss_count,
        winrate_pct=wr,
        profit_factor=pf,
        expectancy_r=exp_r,
        avg_win_r=avg_win_r,
        avg_loss_r=avg_loss_r,
        total_pnl_usd=tot_usd,
        total_pnl_r=tot_r,
    )


def calculate_breakdowns(trades: list[TradeRecordItem]) -> dict[str, list[BreakdownItem]]:
    """Compute multidimensional breakdown metrics (symbol, strategy, session, verdict)."""
    by_symbol_map: dict[str, list[TradeRecordItem]] = {}
    by_strategy_map: dict[str, list[TradeRecordItem]] = {}
    by_session_map: dict[str, list[TradeRecordItem]] = {}
    by_verdict_map: dict[str, list[TradeRecordItem]] = {}

    for t in trades:
        by_symbol_map.setdefault(t.symbol, []).append(t)
        by_strategy_map.setdefault(t.strategy, []).append(t)
        by_session_map.setdefault(t.session, []).append(t)
        by_verdict_map.setdefault(t.verdict, []).append(t)

    return {
        "by_symbol": [_compute_single_breakdown(k, v) for k, v in sorted(by_symbol_map.items())],
        "by_strategy": [
            _compute_single_breakdown(k, v) for k, v in sorted(by_strategy_map.items())
        ],
        "by_session": [_compute_single_breakdown(k, v) for k, v in sorted(by_session_map.items())],
        "by_verdict": [_compute_single_breakdown(k, v) for k, v in sorted(by_verdict_map.items())],
    }


def calculate_indicator_accuracy(
    trades_with_analyses: list[tuple[TradeRecordItem, list[dict[str, Any]]]],
) -> list[IndicatorAccuracyItem]:
    """Compute empirical winrate and performance when each indicator was aligned vs contrarian.

    trades_with_analyses is a list of tuples (trade, indicators_list_from_analysis).
    """
    stats_map: dict[str, dict[str, Any]] = {}

    for name in STANDARD_INDICATOR_NAMES:
        stats_map[name] = {
            "aligned_trades": 0,
            "aligned_wins": 0,
            "aligned_r": 0.0,
            "contrarian_trades": 0,
            "contrarian_wins": 0,
            "contrarian_r": 0.0,
        }

    for trade, indicators in trades_with_analyses:
        is_long = trade.side.upper() == "LONG"
        is_win = trade.pnl_r > 0

        # Create quick lookup by normalized name
        ind_signals: dict[str, str] = {}
        for ind in indicators:
            ind_name = ind.get("name", "")
            ind_sig = ind.get("signal", "NEUTRAL").upper()

            # Map indicator names to standard keys
            for std_name in STANDARD_INDICATOR_NAMES:
                if (
                    std_name.split()[0].lower() in ind_name.lower()
                    or ind_name.lower() in std_name.lower()
                ):
                    ind_signals[std_name] = ind_sig

        for std_name in STANDARD_INDICATOR_NAMES:
            sig = ind_signals.get(std_name, "NEUTRAL")
            if sig == "NEUTRAL":
                continue

            aligned = (is_long and sig == "BULLISH") or (not is_long and sig == "BEARISH")
            contrarian = (is_long and sig == "BEARISH") or (not is_long and sig == "BULLISH")

            if aligned:
                stats_map[std_name]["aligned_trades"] += 1
                if is_win:
                    stats_map[std_name]["aligned_wins"] += 1
                stats_map[std_name]["aligned_r"] += trade.pnl_r
            elif contrarian:
                stats_map[std_name]["contrarian_trades"] += 1
                if is_win:
                    stats_map[std_name]["contrarian_wins"] += 1
                stats_map[std_name]["contrarian_r"] += trade.pnl_r

    result: list[IndicatorAccuracyItem] = []
    for std_name in STANDARD_INDICATOR_NAMES:
        item = stats_map[std_name]
        al_tot = item["aligned_trades"]
        al_win = item["aligned_wins"]
        al_wr = round((al_win / al_tot * 100.0), 2) if al_tot > 0 else 0.0
        al_r = round(item["aligned_r"] / al_tot, 4) if al_tot > 0 else 0.0

        co_tot = item["contrarian_trades"]
        co_win = item["contrarian_wins"]
        co_wr = round((co_win / co_tot * 100.0), 2) if co_tot > 0 else 0.0
        co_r = round(item["contrarian_r"] / co_tot, 4) if co_tot > 0 else 0.0

        net_edge = round(al_wr - co_wr, 2)

        result.append(
            IndicatorAccuracyItem(
                name=std_name,
                aligned_trades=al_tot,
                aligned_wins=al_win,
                aligned_winrate_pct=al_wr,
                aligned_avg_r=al_r,
                contrarian_trades=co_tot,
                contrarian_wins=co_win,
                contrarian_winrate_pct=co_wr,
                contrarian_avg_r=co_r,
                net_edge_pct=net_edge,
            )
        )

    return result


def calculate_macro_filter_impact(
    blocked_items: list[dict[str, Any]],
) -> list[MacroFilterImpactItem]:
    """Compute effectiveness of macro filters (M1..M8) on prevented losses vs missed wins.

    blocked_items: list of dicts with:
      {"blocked_by": list[str], "virtual_pnl_r": float | None}
    """
    map_stats: dict[str, dict[str, Any]] = {}
    for code, name in MACRO_FILTER_DEFINITIONS:
        map_stats[code] = {
            "name": name,
            "blocked_count": 0,
            "virtual_losses_prevented": 0,
            "virtual_wins_missed": 0,
            "net_r_saved": 0.0,
        }

    for item in blocked_items:
        reasons = item.get("blocked_by") or []
        vpnl = item.get("virtual_pnl_r")

        for r_code in reasons:
            code = r_code.upper().strip()
            if code in map_stats:
                map_stats[code]["blocked_count"] += 1
                if vpnl is not None:
                    if vpnl < 0:
                        # Trade would have lost; filter saved us from loss
                        map_stats[code]["virtual_losses_prevented"] += 1
                        map_stats[code]["net_r_saved"] += abs(vpnl)
                    elif vpnl > 0:
                        # Trade would have won; filter caused a missed win
                        map_stats[code]["virtual_wins_missed"] += 1
                        map_stats[code]["net_r_saved"] -= vpnl

    result: list[MacroFilterImpactItem] = []
    for code, _ in MACRO_FILTER_DEFINITIONS:
        st = map_stats[code]
        net_saved = round(st["net_r_saved"], 4)
        if net_saved > 0:
            eff = "Positif (Melindungi Modal)"
        elif net_saved < 0:
            eff = "Perlu Evaluasi"
        else:
            eff = "Netral"

        result.append(
            MacroFilterImpactItem(
                code=code,
                name=st["name"],
                blocked_count=st["blocked_count"],
                virtual_losses_prevented=st["virtual_losses_prevented"],
                virtual_wins_missed=st["virtual_wins_missed"],
                net_r_saved=net_saved,
                effectiveness=eff,
            )
        )

    return result


def calculate_slippage_stats(
    executions: list[RealExecutionRecord],
    tickets_map: dict[int, TicketRecord],
) -> SlippageStats:
    """Calculate slippage statistics between ticket planned entry and actual fill price."""
    if not executions:
        return SlippageStats()

    slippages = [e.slippage_points for e in executions]
    avg_slip = round(statistics.mean(slippages), 4) if slippages else 0.0
    med_slip = round(statistics.median(slippages), 4) if slippages else 0.0
    min_slip = round(min(slippages), 4) if slippages else 0.0
    max_slip = round(max(slippages), 4) if slippages else 0.0

    # Total slippage cost in USD:
    # slippage * lot * contract_size
    total_cost_usd = 0.0
    broker_map: dict[str, list[tuple[float, float]]] = {}  # profile -> list of (slippage, cost_usd)
    symbol_map: dict[str, list[tuple[float, float]]] = {}  # symbol -> list of (slippage, cost_usd)

    for e in executions:
        ticket = tickets_map.get(e.ticket_id)
        symbol = ticket.symbol if ticket else "UNKNOWN"
        contract_size = 100.0 if "XAU" in symbol.upper() else 1.0

        # Cost in USD: adverse slippage costs money
        cost = e.slippage_points * e.lot * contract_size
        total_cost_usd += cost

        broker_map.setdefault(e.broker_profile, []).append((e.slippage_points, cost))
        symbol_map.setdefault(symbol, []).append((e.slippage_points, cost))

    by_broker: list[BrokerSlippageItem] = []
    for b_name, pairs in sorted(broker_map.items()):
        b_slips = [p[0] for p in pairs]
        b_costs = sum(p[1] for p in pairs)
        by_broker.append(
            BrokerSlippageItem(
                broker_profile=b_name,
                total_executions=len(pairs),
                avg_slippage_points=round(statistics.mean(b_slips), 4),
                total_slippage_cost_usd=round(b_costs, 2),
            )
        )

    by_symbol: list[SymbolSlippageItem] = []
    for s_name, pairs in sorted(symbol_map.items()):
        s_slips = [p[0] for p in pairs]
        s_costs = sum(p[1] for p in pairs)
        by_symbol.append(
            SymbolSlippageItem(
                symbol=s_name,
                total_executions=len(pairs),
                avg_slippage_points=round(statistics.mean(s_slips), 4),
                total_slippage_cost_usd=round(s_costs, 2),
            )
        )

    return SlippageStats(
        total_executions=len(executions),
        avg_slippage_points=avg_slip,
        median_slippage_points=med_slip,
        min_slippage_points=min_slip,
        max_slippage_points=max_slip,
        total_slippage_cost_usd=round(total_cost_usd, 2),
        by_broker=by_broker,
        by_symbol=by_symbol,
    )
