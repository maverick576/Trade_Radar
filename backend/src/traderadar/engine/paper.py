"""Paper trading engine according to BLUEPRINT.md §5.5 and SIGNAL_ENGINE.md §7 & §9.

Handles simulated order execution, taker fees, TP1 (50% + SL->BE), TP2 (remaining 50%),
same-candle SL priority, time stop (32 bars), opposite exit, daily loss limit,
and virtual simulation for blocked signals.
"""

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from traderadar.core.time import utc_now

WIB = ZoneInfo("Asia/Jakarta")


class CandleBar(BaseModel):
    """Bar structure for paper trade evaluation."""

    open_time: datetime
    open: float
    high: float
    low: float
    close: float


class PaperTradeState(BaseModel):
    """Active or closed paper trade position."""

    id: int | None = None
    ticket_id: int | None = None
    signal_id: int | None = None
    strategy: str = "konfluensi10"
    symbol: str
    side: Literal["LONG", "SHORT"]
    entry_time: datetime
    entry_price: float
    size: float  # In asset units
    initial_sl: float
    current_sl: float
    tp1: float
    tp2: float
    r_distance: float
    tp1_hit: bool = False
    bars_held: int = 0
    status: Literal["OPEN", "CLOSED"] = "OPEN"
    exit_time: datetime | None = None
    exit_price: float | None = None
    # "SL", "BE", "TP1", "TP2", "TIME_STOP", "OPPOSITE_SIGNAL", "MANUAL"
    exit_reason: str | None = None
    pnl_usd: float | None = None
    pnl_r: float | None = None
    fees_usd: float = 0.0
    mfe_r: float = 0.0
    mae_r: float = 0.0
    is_virtual: bool = False  # True for simulated blocked signals
    created_at: datetime = Field(default_factory=utc_now)


def calculate_paper_entry_price(
    open_price: float,
    side: Literal["LONG", "SHORT"],
    slippage_bps: int = 2,
) -> float:
    """Calculate entry execution price factoring taker slippage (default 2 bps = 0.02%)."""
    slippage_mult = slippage_bps / 10000.0
    if side == "LONG":
        return open_price * (1.0 + slippage_mult)
    else:
        return open_price * (1.0 - slippage_mult)


def create_paper_position(
    symbol: str,
    side: Literal["LONG", "SHORT"],
    bar_open: float,
    bar_time: datetime,
    sl: float,
    tp1: float,
    tp2: float,
    equity: float = 1000.0,
    risk_pct: float = 1.0,
    strategy: str = "konfluensi10",
    ticket_id: int | None = None,
    signal_id: int | None = None,
    slippage_bps: int = 2,
    taker_fee_rate: float = 0.0005,  # 0.05% taker fee
    is_virtual: bool = False,
) -> PaperTradeState:
    """Open a simulated paper trading position."""
    entry_price = calculate_paper_entry_price(bar_open, side, slippage_bps)
    r = abs(entry_price - sl)
    if r <= 0:
        r = 1e-4

    risk_usd = equity * (risk_pct / 100.0)
    size = risk_usd / r

    # Entry fee (taker)
    entry_fee = size * entry_price * taker_fee_rate

    return PaperTradeState(
        ticket_id=ticket_id,
        signal_id=signal_id,
        strategy=strategy,
        symbol=symbol,
        side=side,
        entry_time=bar_time,
        entry_price=round(entry_price, 4),
        size=round(size, 6),
        initial_sl=sl,
        current_sl=sl,
        tp1=tp1,
        tp2=tp2,
        r_distance=round(r, 4),
        tp1_hit=False,
        bars_held=0,
        status="OPEN",
        fees_usd=round(entry_fee, 4),
        mfe_r=0.0,
        mae_r=0.0,
        is_virtual=is_virtual,
    )


def update_paper_position_with_bar(
    trade: PaperTradeState,
    bar: CandleBar,
    time_stop_bars: int = 32,
    taker_fee_rate: float = 0.0005,
) -> PaperTradeState:
    """Evaluate an open paper position against a newly closed candlestick bar."""
    if trade.status != "OPEN":
        return trade

    t = trade.model_copy(deep=True)
    t.bars_held += 1

    r = t.r_distance

    if t.side == "LONG":
        # Calculate excursion
        candle_mfe = (bar.high - t.entry_price) / r
        candle_mae = (bar.low - t.entry_price) / r
        t.mfe_r = round(max(t.mfe_r, candle_mfe), 4)
        t.mae_r = round(min(t.mae_r, candle_mae), 4)

        sl_hit = bar.low <= t.current_sl
        tp1_reached = bar.high >= t.tp1
        tp2_reached = bar.high >= t.tp2

        # Invariant: If both SL and TP hit in the same candle -> SL hit first!
        if sl_hit and (tp1_reached or tp2_reached) and not t.tp1_hit:
            return _close_paper_trade(
                trade=t,
                exit_price=t.current_sl,
                exit_time=bar.open_time,
                exit_reason="SL",
                taker_fee_rate=taker_fee_rate,
            )

        # Normal SL hit
        if sl_hit:
            exit_reason = "BE" if t.tp1_hit else "SL"
            return _close_paper_trade(
                trade=t,
                exit_price=t.current_sl,
                exit_time=bar.open_time,
                exit_reason=exit_reason,
                taker_fee_rate=taker_fee_rate,
            )

        # TP1 hit
        if tp1_reached and not t.tp1_hit:
            t.tp1_hit = True
            t.current_sl = t.entry_price  # Move SL to Breakeven

            # Check if TP2 also hit in the same candle after TP1
            if tp2_reached:
                return _close_paper_trade(
                    trade=t,
                    exit_price=t.tp2,
                    exit_time=bar.open_time,
                    exit_reason="TP2",
                    taker_fee_rate=taker_fee_rate,
                )

        # TP2 hit after TP1
        elif tp2_reached and t.tp1_hit:
            return _close_paper_trade(
                trade=t,
                exit_price=t.tp2,
                exit_time=bar.open_time,
                exit_reason="TP2",
                taker_fee_rate=taker_fee_rate,
            )

    else:  # SHORT
        # Calculate excursion
        candle_mfe = (t.entry_price - bar.low) / r
        candle_mae = (t.entry_price - bar.high) / r
        t.mfe_r = round(max(t.mfe_r, candle_mfe), 4)
        t.mae_r = round(min(t.mae_r, candle_mae), 4)

        sl_hit = bar.high >= t.current_sl
        tp1_reached = bar.low <= t.tp1
        tp2_reached = bar.low <= t.tp2

        # Same candle priority: SL first
        if sl_hit and (tp1_reached or tp2_reached) and not t.tp1_hit:
            return _close_paper_trade(
                trade=t,
                exit_price=t.current_sl,
                exit_time=bar.open_time,
                exit_reason="SL",
                taker_fee_rate=taker_fee_rate,
            )

        if sl_hit:
            exit_reason = "BE" if t.tp1_hit else "SL"
            return _close_paper_trade(
                trade=t,
                exit_price=t.current_sl,
                exit_time=bar.open_time,
                exit_reason=exit_reason,
                taker_fee_rate=taker_fee_rate,
            )

        if tp1_reached and not t.tp1_hit:
            t.tp1_hit = True
            t.current_sl = t.entry_price

            if tp2_reached:
                return _close_paper_trade(
                    trade=t,
                    exit_price=t.tp2,
                    exit_time=bar.open_time,
                    exit_reason="TP2",
                    taker_fee_rate=taker_fee_rate,
                )
        elif tp2_reached and t.tp1_hit:
            return _close_paper_trade(
                trade=t,
                exit_price=t.tp2,
                exit_time=bar.open_time,
                exit_reason="TP2",
                taker_fee_rate=taker_fee_rate,
            )

    # Time-stop check
    if t.bars_held >= time_stop_bars:
        return _close_paper_trade(
            trade=t,
            exit_price=bar.close,
            exit_time=bar.open_time,
            exit_reason="TIME_STOP",
            taker_fee_rate=taker_fee_rate,
        )

    return t


def close_paper_trade_opposite(
    trade: PaperTradeState,
    exit_price: float,
    exit_time: datetime,
    taker_fee_rate: float = 0.0005,
) -> PaperTradeState:
    """Close an open paper trade due to an opposite STRONG signal."""
    return _close_paper_trade(
        trade=trade,
        exit_price=exit_price,
        exit_time=exit_time,
        exit_reason="OPPOSITE_SIGNAL",
        taker_fee_rate=taker_fee_rate,
    )


def close_paper_trade_manual(
    trade: PaperTradeState,
    exit_price: float,
    exit_time: datetime,
    taker_fee_rate: float = 0.0005,
) -> PaperTradeState:
    """Manually close an open paper trade from UI or command."""
    return _close_paper_trade(
        trade=trade,
        exit_price=exit_price,
        exit_time=exit_time,
        exit_reason="MANUAL",
        taker_fee_rate=taker_fee_rate,
    )


def _close_paper_trade(
    trade: PaperTradeState,
    exit_price: float,
    exit_time: datetime,
    exit_reason: str,
    taker_fee_rate: float = 0.0005,
) -> PaperTradeState:
    """Helper to finalize trade metrics on exit."""
    t = trade.model_copy(deep=True)
    t.status = "CLOSED"
    t.exit_price = round(exit_price, 4)
    t.exit_time = exit_time
    t.exit_reason = exit_reason

    # Exit taker fee
    exit_fee = t.size * exit_price * taker_fee_rate
    t.fees_usd = round(t.fees_usd + exit_fee, 4)

    r = t.r_distance

    # Calculate PnL based on TP1 split or full exit
    if t.tp1_hit:
        # 50% was closed at TP1 (+1.0 R)
        tp1_r = 1.0
        # Remaining 50% closed at exit_price
        if t.side == "LONG":
            rem_r = (exit_price - t.entry_price) / r
        else:
            rem_r = (t.entry_price - exit_price) / r

        pnl_r = 0.5 * tp1_r + 0.5 * rem_r
        gross_pnl_usd = pnl_r * (t.size * r)
    else:
        if t.side == "LONG":
            pnl_points = exit_price - t.entry_price
        else:
            pnl_points = t.entry_price - exit_price

        pnl_r = pnl_points / r
        gross_pnl_usd = t.size * pnl_points

    net_pnl_usd = gross_pnl_usd - t.fees_usd
    t.pnl_usd = round(net_pnl_usd, 2)
    t.pnl_r = round(pnl_r, 4)

    return t


def check_daily_loss_limit(
    closed_trades_today: list[PaperTradeState],
    initial_equity: float = 1000.0,
    daily_loss_limit_pct: float = 3.0,
) -> tuple[bool, float]:
    """Check if cumulative realized loss today exceeds daily loss limit.

    Returns (is_exceeded, daily_realized_pnl_usd).
    """
    realized_usd = sum(
        (tr.pnl_usd or 0.0)
        for tr in closed_trades_today
        if not tr.is_virtual and tr.status == "CLOSED"
    )

    max_loss_usd = -(initial_equity * (daily_loss_limit_pct / 100.0))
    is_exceeded = realized_usd <= max_loss_usd
    return is_exceeded, round(realized_usd, 2)
