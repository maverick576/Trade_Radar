"""Risk management and level calculation according to SIGNAL_ENGINE.md §7."""

import math
from typing import Literal

from pydantic import BaseModel

from traderadar.core.config import RiskSettings, TicketSettings

TICK_SIZES: dict[str, float] = {
    "BTCUSDT": 0.1,
    "ETHUSDT": 0.01,
    "SOLUSDT": 0.01,
    "XAUUSD": 0.1,
    "XAUUSDT": 0.1,
    "PAXGUSDT": 0.01,
}


def round_to_tick(val: float, tick_size: float = 0.1) -> float:
    """Round value to the symbol's market tick size."""
    if tick_size <= 0:
        return round(val, 2)
    precision = max(0, -int(math.floor(math.log10(tick_size))))
    steps = round(val / tick_size)
    return round(steps * tick_size, precision)


def floor_to_step(val: float, step: float = 0.01) -> float:
    """Round value strictly down to broker lot step size."""
    if step <= 0:
        return val
    precision = max(0, -int(math.floor(math.log10(step))))
    steps = math.floor(round(val / step, 6))
    return round(steps * step, precision)


class LotCalculationResult(BaseModel):
    """Result of broker lot sizing calculation."""

    lot: float
    raw_lot: float
    risk_usd: float
    actual_risk_usd: float
    actual_risk_pct: float
    min_lot_warning: bool
    warning_message: str | None = None


def calculate_lot_size(
    balance: float,
    risk_pct: float,
    contract_size: float,
    min_lot: float,
    lot_step: float,
    entry: float,
    sl: float,
) -> LotCalculationResult:
    """Calculate position lot size according to broker profile and risk parameters.

    Formula from SIGNAL_ENGINE.md §7b:
    risk_usd = balance * (risk_pct / 100)
    sl_distance = |entry - sl|
    sl_usd_per_lot = sl_distance * contract_size
    lot = floor_to_step(risk_usd / sl_usd_per_lot, lot_step)
    If lot < min_lot: warn and clamp to min_lot (risiko aktual > batas).
    """
    if balance <= 0:
        raise ValueError("Balance must be positive")
    if risk_pct <= 0:
        raise ValueError("Risk percentage must be positive")
    if contract_size <= 0:
        raise ValueError("Contract size must be positive")

    sl_dist = abs(entry - sl)
    if sl_dist <= 0:
        raise ValueError("Stop loss distance must be greater than zero")

    risk_usd = balance * (risk_pct / 100.0)
    sl_usd_per_lot = sl_dist * contract_size
    raw_lot = risk_usd / sl_usd_per_lot

    calculated_lot = floor_to_step(raw_lot, lot_step)
    min_lot_warning = False
    warning_message = None

    if calculated_lot < min_lot:
        actual_lot = min_lot
        min_lot_warning = True
        actual_risk_usd = round(actual_lot * sl_usd_per_lot, 2)
        actual_risk_pct = round((actual_risk_usd / balance) * 100.0, 2)
        warning_message = (
            f"Risiko aktual {actual_risk_pct:.2f}% > batas {risk_pct:.2f}% "
            f"(lot minimum {min_lot})"
        )
    else:
        actual_lot = calculated_lot
        actual_risk_usd = round(actual_lot * sl_usd_per_lot, 2)
        actual_risk_pct = round((actual_risk_usd / balance) * 100.0, 2)

    return LotCalculationResult(
        lot=actual_lot,
        raw_lot=round(raw_lot, 6),
        risk_usd=round(risk_usd, 2),
        actual_risk_usd=actual_risk_usd,
        actual_risk_pct=actual_risk_pct,
        min_lot_warning=min_lot_warning,
        warning_message=warning_message,
    )


class TradeLevels(BaseModel):
    """Calculated entry, SL, TP, and invalidation levels."""

    entry: float
    entry_low: float
    entry_high: float
    sl: float
    tp1: float
    tp2: float
    r_distance: float
    atr: float
    sl_points: float
    sl_atr_mult: float
    tp1_points: float
    tp2_points: float
    invalidation: str


def calculate_trade_levels(
    symbol: str,
    side: Literal["LONG", "SHORT"],
    entry_price: float,
    atr14: float,
    swing_low_10: float | None = None,
    swing_high_10: float | None = None,
    supertrend_level: float | None = None,
    risk_settings: RiskSettings | None = None,
    ticket_settings: TicketSettings | None = None,
) -> TradeLevels:
    """Calculate SL, TP1, TP2, entry zone, and invalidation levels.

    Rules from SIGNAL_ENGINE.md §7:
    ATR = ATR14 M15
    SL  = entry - 1.5 * ATR (LONG), or below 10-bar swing low if further but <= 2.5 * ATR.
    For SHORT: entry + 1.5 * ATR, or above 10-bar swing high if further but <= 2.5 * ATR.
    R   = |entry - SL|
    TP1 = entry + 1.0 * R (LONG) / entry - 1.0 * R (SHORT)
    TP2 = entry + 2.0 * R (LONG) / entry - 2.0 * R (SHORT)
    """
    risk_cfg = risk_settings or RiskSettings()
    ticket_cfg = ticket_settings or TicketSettings()
    tick = TICK_SIZES.get(symbol.upper(), 0.1)

    atr = max(atr14, 1e-4)

    # Base SL distance (default 1.5 * ATR)
    base_sl_dist = risk_cfg.sl_atr_mult * atr
    max_sl_dist = risk_cfg.sl_max_atr_mult * atr

    if side == "LONG":
        chosen_dist = base_sl_dist
        if swing_low_10 is not None:
            swing_dist = entry_price - swing_low_10
            # If swing low is further than 1.5*ATR but <= 2.5*ATR, use swing low
            if swing_dist > base_sl_dist and swing_dist <= max_sl_dist:
                chosen_dist = swing_dist

        raw_sl = entry_price - chosen_dist
        sl = round_to_tick(raw_sl, tick)
        r = abs(entry_price - sl)
        tp1 = round_to_tick(entry_price + (risk_cfg.tp1_r * r), tick)
        tp2 = round_to_tick(entry_price + (risk_cfg.tp2_r * r), tick)

        entry_low = round_to_tick(entry_price - (ticket_cfg.entry_zone_atr * atr), tick)
        entry_high = round_to_tick(entry_price + (ticket_cfg.entry_zone_atr * atr), tick)

        # Invalidation explanation
        inv_level = supertrend_level or sl
        invalidation = f"close M15 di bawah {inv_level:.1f} (Supertrend/Structure)"

    else:  # SHORT
        chosen_dist = base_sl_dist
        if swing_high_10 is not None:
            swing_dist = swing_high_10 - entry_price
            if swing_dist > base_sl_dist and swing_dist <= max_sl_dist:
                chosen_dist = swing_dist

        raw_sl = entry_price + chosen_dist
        sl = round_to_tick(raw_sl, tick)
        r = abs(sl - entry_price)
        tp1 = round_to_tick(entry_price - (risk_cfg.tp1_r * r), tick)
        tp2 = round_to_tick(entry_price - (risk_cfg.tp2_r * r), tick)

        entry_low = round_to_tick(entry_price - (ticket_cfg.entry_zone_atr * atr), tick)
        entry_high = round_to_tick(entry_price + (ticket_cfg.entry_zone_atr * atr), tick)

        inv_level = supertrend_level or sl
        invalidation = f"close M15 di atas {inv_level:.1f} (Supertrend/Structure)"

    sl_points = round(abs(entry_price - sl), 2)
    sl_atr_mult = round(sl_points / atr, 2)
    tp1_points = round(abs(tp1 - entry_price), 2)
    tp2_points = round(abs(tp2 - entry_price), 2)

    return TradeLevels(
        entry=round_to_tick(entry_price, tick),
        entry_low=entry_low,
        entry_high=entry_high,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        r_distance=round(r, 4),
        atr=round(atr, 4),
        sl_points=sl_points,
        sl_atr_mult=sl_atr_mult,
        tp1_points=tp1_points,
        tp2_points=tp2_points,
        invalidation=invalidation,
    )
