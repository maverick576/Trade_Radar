"""Trade Ticket creation, broker calibration, and formatting.

Reference: BLUEPRINT.md §5.3 & SIGNAL_ENGINE.md §7b.
"""

from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from traderadar.core.config import BrokerProfile, RiskSettings, TicketSettings
from traderadar.core.time import utc_now
from traderadar.engine.risk import (
    TICK_SIZES,
    LotCalculationResult,
    calculate_lot_size,
    calculate_trade_levels,
    round_to_tick,
)

WIB = ZoneInfo("Asia/Jakarta")


def format_id_number(val: float, decimals: int = 1) -> str:
    """Format float into Indonesian locale number (dots for thousands, commas for decimals)."""
    formatted = f"{val:,.{decimals}f}"
    # Swap , and . (e.g. 2,651.0 -> 2.651,0)
    return formatted.replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")


class TradeTicket(BaseModel):
    """Execution-ready trade ticket."""

    id: int | None = None
    signal_id: int | None = None
    symbol: str
    side: Literal["LONG", "SHORT"]
    strategy: str = "Konfluensi-10"
    score: float = 0.0
    source: str = "Binance"
    entry: float
    entry_low: float
    entry_high: float
    sl: float
    tp1: float
    tp2: float
    atr: float
    sl_points: float
    sl_atr_mult: float
    tp1_points: float
    tp2_points: float
    invalidation: str
    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    valid_until: datetime
    status: Literal["new", "executed", "skipped", "expired", "closed"] = "new"
    broker_offset: float | None = None
    broker_profile: str | None = None
    suggested_lot: float | None = None
    actual_risk_usd: float | None = None
    actual_risk_pct: float | None = None
    min_lot_warning: bool = False
    warning_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class BrokerCalibration(BaseModel):
    """Broker price calibration record (valid for 30 minutes)."""

    id: int | None = None
    symbol: str
    broker_profile: str
    broker_price: float
    source_price: float
    offset: float
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return utc_now() > self.expires_at


def create_trade_ticket(
    symbol: str,
    side: Literal["LONG", "SHORT"],
    entry_price: float,
    atr14: float,
    score: float = 0.0,
    strategy: str = "Konfluensi-10",
    source: str = "Binance XAUUSDT",
    bar_time: datetime | None = None,
    signal_id: int | None = None,
    swing_low_10: float | None = None,
    swing_high_10: float | None = None,
    supertrend_level: float | None = None,
    reasons: list[str] | None = None,
    risks: list[str] | None = None,
    risk_settings: RiskSettings | None = None,
    ticket_settings: TicketSettings | None = None,
    broker_profile: BrokerProfile | None = None,
    broker_offset: float | None = None,
) -> TradeTicket:
    """Create a new TradeTicket from technical analysis levels."""
    risk_cfg = risk_settings or RiskSettings()
    ticket_cfg = ticket_settings or TicketSettings()
    ref_time = bar_time or utc_now()
    valid_until = ref_time + timedelta(minutes=15 * ticket_cfg.valid_bars)

    levels = calculate_trade_levels(
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        atr14=atr14,
        swing_low_10=swing_low_10,
        swing_high_10=swing_high_10,
        supertrend_level=supertrend_level,
        risk_settings=risk_cfg,
        ticket_settings=ticket_cfg,
    )

    clean_symbol = symbol.replace("USDT", "").replace("_", "")
    if clean_symbol == "XAU":
        clean_symbol = "XAUUSD"

    suggested_lot = None
    actual_risk_usd = None
    actual_risk_pct = None
    min_lot_warning = False
    warning_message = None

    if broker_profile and clean_symbol in broker_profile.symbols:
        sym_cfg = broker_profile.symbols[clean_symbol]
        lot_res = calculate_lot_size(
            balance=broker_profile.balance,
            risk_pct=broker_profile.risk_pct,
            contract_size=sym_cfg.contract_size,
            min_lot=sym_cfg.min_lot,
            lot_step=sym_cfg.lot_step,
            entry=levels.entry,
            sl=levels.sl,
        )
        suggested_lot = lot_res.lot
        actual_risk_usd = lot_res.actual_risk_usd
        actual_risk_pct = lot_res.actual_risk_pct
        min_lot_warning = lot_res.min_lot_warning
        warning_message = lot_res.warning_message

    ticket = TradeTicket(
        signal_id=signal_id,
        symbol=clean_symbol,
        side=side,
        strategy=strategy,
        score=score,
        source=source,
        entry=levels.entry,
        entry_low=levels.entry_low,
        entry_high=levels.entry_high,
        sl=levels.sl,
        tp1=levels.tp1,
        tp2=levels.tp2,
        atr=levels.atr,
        sl_points=levels.sl_points,
        sl_atr_mult=levels.sl_atr_mult,
        tp1_points=levels.tp1_points,
        tp2_points=levels.tp2_points,
        invalidation=levels.invalidation,
        reasons=reasons or [],
        risks=risks or [],
        valid_until=valid_until,
        status="new",
        broker_offset=broker_offset,
        broker_profile=broker_profile.name if broker_profile else None,
        suggested_lot=suggested_lot,
        actual_risk_usd=actual_risk_usd,
        actual_risk_pct=actual_risk_pct,
        min_lot_warning=min_lot_warning,
        warning_message=warning_message,
    )

    if broker_offset is not None and broker_offset != 0.0:
        return apply_broker_offset(ticket, broker_offset)

    return ticket


def apply_broker_offset(ticket: TradeTicket, offset: float) -> TradeTicket:
    """Adjust ticket entry, SL, and TP levels by adding the broker calibration offset."""
    tick = TICK_SIZES.get(ticket.symbol.upper(), 0.1)
    new_ticket = ticket.model_copy(deep=True)
    new_ticket.broker_offset = offset
    new_ticket.entry = round_to_tick(ticket.entry + offset, tick)
    new_ticket.entry_low = round_to_tick(ticket.entry_low + offset, tick)
    new_ticket.entry_high = round_to_tick(ticket.entry_high + offset, tick)
    new_ticket.sl = round_to_tick(ticket.sl + offset, tick)
    new_ticket.tp1 = round_to_tick(ticket.tp1 + offset, tick)
    new_ticket.tp2 = round_to_tick(ticket.tp2 + offset, tick)
    return new_ticket


def check_ticket_expiration(
    ticket: TradeTicket,
    current_time: datetime,
    current_price: float,
    chase_limit_atr: float = 0.5,
) -> tuple[bool, str | None]:
    """Check whether a ticket is expired by time or market price chasing.

    Rules:
    - current_time >= valid_until -> EXPIRED_TIME
    - price moved beyond entry zone by > 0.5 * ATR in the trade direction -> CHASE_LIMIT
    - price touched SL before entry -> SL_HIT_BEFORE_ENTRY
    """
    if current_time >= ticket.valid_until:
        return True, "EXPIRED_TIME"

    chase_buffer = chase_limit_atr * ticket.atr

    if ticket.side == "LONG":
        if current_price > (ticket.entry_high + chase_buffer):
            return True, "CHASE_LIMIT"
        if current_price <= ticket.sl:
            return True, "SL_HIT_BEFORE_ENTRY"
    else:  # SHORT
        if current_price < (ticket.entry_low - chase_buffer):
            return True, "CHASE_LIMIT"
        if current_price >= ticket.sl:
            return True, "SL_HIT_BEFORE_ENTRY"

    return False, None


def format_ticket_full(
    ticket: TradeTicket,
    broker_profile: BrokerProfile | None = None,
    broker_offset: float | None = None,
    lot_result: LotCalculationResult | None = None,
) -> str:
    """Format full ticket text matching BLUEPRINT.md §5.3 specification."""
    side_icon = "🟢 BUY" if ticket.side == "LONG" else "🔴 SELL"
    score_str = f"skor {int(round(ticket.score))}"

    valid_until_wib = ticket.valid_until.astimezone(WIB)
    valid_str = f"Berlaku s/d {valid_until_wib.strftime('%H:%M')} WIB (3 bar)"

    offset_val = broker_offset if broker_offset is not None else ticket.broker_offset
    source_str = f"Sumber harga: {ticket.source}"
    if offset_val is not None and offset_val != 0.0:
        sign = "+" if offset_val > 0 else ""
        source_str += f" (disesuaikan untuk broker {sign}{format_id_number(offset_val, 1)})"

    # Display levels
    disp_entry = ticket.entry
    disp_low = ticket.entry_low
    disp_high = ticket.entry_high
    disp_sl = ticket.sl
    disp_tp1 = ticket.tp1
    disp_tp2 = ticket.tp2

    dec = 1 if ticket.symbol.startswith("XAU") or ticket.symbol.startswith("BTC") else 2

    e_str = format_id_number(disp_entry, dec)
    el_str = format_id_number(disp_low, dec)
    eh_str = format_id_number(disp_high, dec)
    entry_line = f"Entry   : {e_str}  (zona {el_str} – {eh_str})     ← market bila harga di zona"

    sl_sign = "−" if ticket.side == "LONG" else "+"
    sl_p = format_id_number(ticket.sl_points, dec)
    sl_atr = format_id_number(ticket.sl_atr_mult, 1)
    sl_line = f"SL      : {format_id_number(disp_sl, dec)}  ({sl_sign}{sl_p} · {sl_atr}×ATR)"
    tp1_line = f"TP1     : {format_id_number(disp_tp1, dec)}  (+1R, tutup 50%, SL → BE)"
    tp2_line = f"TP2     : {format_id_number(disp_tp2, dec)}  (+2R)"

    # Lot line
    lot_line = ""
    lot_calc = lot_result

    if lot_calc:
        lot_f = format_id_number(lot_calc.lot, 2)
        bal_f = f"${int(round(broker_profile.balance)):,}" if broker_profile else "$10.000"
        risk_pct_val = int(broker_profile.risk_pct) if broker_profile else 1
        r_usd = int(round(lot_calc.risk_usd))
        act_usd = int(round(lot_calc.actual_risk_usd))
        lot_line = (
            f"Lot     : {lot_f} lot (risiko {risk_pct_val}% dari {bal_f} = "
            f"${r_usd} → aktual ${act_usd})  ← kalkulator broker"
        )
        if lot_calc.min_lot_warning:
            lot_line += f"\n⚠ {lot_calc.warning_message}"
    elif ticket.suggested_lot is not None:
        lot_f = format_id_number(ticket.suggested_lot, 2)
        bal_str = "$10.000"
        risk_usd = 100
        actual_usd = int(round(ticket.actual_risk_usd or 87))
        lot_line = (
            f"Lot     : {lot_f} lot (risiko 1% dari {bal_str} = "
            f"${risk_usd} → aktual ${actual_usd})  ← kalkulator broker"
        )
        if ticket.min_lot_warning and ticket.warning_message:
            lot_line += f"\n⚠ {ticket.warning_message}"
    else:
        lot_line = "Lot     : - (pilih profil broker)"

    inv_line = f"Invalidasi: {ticket.invalidation}"
    reasons_str = " · ".join(ticket.reasons) if ticket.reasons else "Konfluensi teknikal"
    reasons_line = f"Alasan  : {reasons_str}"
    risks_str = " · ".join(ticket.risks) if ticket.risks else "Perhatikan volatilitas pasar"
    risks_line = f"Risiko  : {risks_str}"

    lines = [
        f"{side_icon} {ticket.symbol} · M15 · {ticket.strategy} · {score_str}",
        f"{valid_str} · {source_str}",
        entry_line,
        sl_line,
        tp1_line,
        tp2_line,
        lot_line,
        inv_line,
        reasons_line,
        risks_line,
    ]
    return "\n".join(lines)


def format_ticket_compact(
    ticket: TradeTicket,
    broker_offset: float | None = None,
    lot_result: LotCalculationResult | None = None,
) -> str:
    """Format single line compact ticket matching BLUEPRINT.md §5.3.

    Example: `BUY XAUUSD 2651 SL 2636.5 TP 2665.5/2680 0.06lot`
    """
    action = "BUY" if ticket.side == "LONG" else "SELL"
    entry_val = ticket.entry if broker_offset is None else ticket.entry + broker_offset
    sl_val = ticket.sl if broker_offset is None else ticket.sl + broker_offset
    tp1_val = ticket.tp1 if broker_offset is None else ticket.tp1 + broker_offset
    tp2_val = ticket.tp2 if broker_offset is None else ticket.tp2 + broker_offset

    def strip_zero(n: float) -> str:
        s = f"{n:.1f}"
        return s[:-2] if s.endswith(".0") else s

    lot = lot_result.lot if lot_result else (ticket.suggested_lot or 0.01)
    lot_str = f"{lot:.2f}".rstrip("0").rstrip(".") if lot >= 0.1 else f"{lot:.2f}"

    return (
        f"{action} {ticket.symbol} {strip_zero(entry_val)} "
        f"SL {strip_zero(sl_val)} TP {strip_zero(tp1_val)}/{strip_zero(tp2_val)} {lot_str}lot"
    )
