"""Unit tests for Trade Ticket creation, lot sizing, and formatting.

Acceptance criteria verification for BLUEPRINT.md §5.3:
Entry 2651.0, SL 2636.5, TP 2665.5 / 2680.0, 0.06 lot for $10,000 balance (actual risk $87).
"""

from datetime import UTC, datetime, timedelta

from traderadar.core.config import BrokerProfile, BrokerSymbolConfig
from traderadar.engine.risk import (
    calculate_lot_size,
    round_to_tick,
)
from traderadar.engine.ticket import (
    BrokerCalibration,
    apply_broker_offset,
    check_ticket_expiration,
    create_trade_ticket,
    format_ticket_compact,
    format_ticket_full,
)


def test_blueprint_example_exact_reproduction() -> None:
    """Verify that the exact example from BLUEPRINT.md §5.3 is reproduced by the engine:

    Entry: 2651.0
    SL: 2636.5 (-14.5 points, 1.5xATR)
    TP1: 2665.5 (+1R, close 50%, SL -> BE)
    TP2: 2680.0 (+2R)
    Lot: 0.06 lot (1% risk of $10,000 = $100 -> actual $87)
    """
    symbol = "XAUUSD"
    entry = 2651.0
    # 1.5 * atr = 14.5 -> atr = 14.5 / 1.5 = 9.666666666666666
    atr14 = 14.5 / 1.5
    side = "LONG"

    # Broker profile (Exness Standard, Gold 100 oz contract)
    profile = BrokerProfile(
        name="Exness Standard",
        account_currency="USD",
        balance=10000.0,
        risk_pct=1.0,
        symbols={
            "XAUUSD": BrokerSymbolConfig(
                broker_symbol="XAUUSDm",
                contract_size=100.0,
                min_lot=0.01,
                lot_step=0.01,
            )
        },
    )

    ticket_time = datetime(2026, 10, 15, 1, 0, tzinfo=UTC)  # 08:00 WIB -> valid until 08:45 WIB
    ticket = create_trade_ticket(
        symbol=symbol,
        side=side,
        entry_price=entry,
        atr14=atr14,
        score=62.0,
        strategy="Konfluensi-10",
        source="Binance XAUUSDT",
        bar_time=ticket_time,
        supertrend_level=2640.0,
        reasons=["EMA ribbon & Supertrend bullish H1/M15", "CVD naik", "di atas VWAP"],
        risks=["CPI USD 19:30 WIB besok", "RSI dekat overbought"],
        broker_profile=profile,
    )

    # 1. Verify Level calculations
    assert ticket.entry == 2651.0
    assert ticket.sl == 2636.5
    assert ticket.tp1 == 2665.5
    assert ticket.tp2 == 2680.0
    assert ticket.sl_points == 14.5
    assert ticket.sl_atr_mult == 1.5

    # 2. Verify Lot calculation
    assert ticket.suggested_lot == 0.06
    assert ticket.actual_risk_usd == 87.0
    assert ticket.actual_risk_pct == 0.87
    assert ticket.min_lot_warning is False

    # 3. Verify Full Ticket formatting matches BLUEPRINT.md §5.3
    full_text = format_ticket_full(ticket, broker_profile=profile)
    assert "🟢 BUY XAUUSD · M15 · Konfluensi-10 · skor 62" in full_text
    assert "08:45 WIB (3 bar) · Sumber harga: Binance XAUUSDT" in full_text
    assert "Entry   : 2.651,0  (zona 2.650,0 – 2.652,0)" in full_text
    assert "SL      : 2.636,5  (−14,5 · 1,5×ATR)" in full_text
    assert "TP1     : 2.665,5  (+1R, tutup 50%, SL → BE)" in full_text
    assert "TP2     : 2.680,0  (+2R)" in full_text
    assert "Lot     : 0,06 lot (risiko 1% dari $10.000 = $100 → aktual $87)" in full_text
    assert "Invalidasi: close M15 di bawah 2640.0" in full_text
    assert "Alasan  : EMA ribbon & Supertrend bullish H1/M15 · CVD naik · di atas VWAP" in full_text
    assert "Risiko  : CPI USD 19:30 WIB besok · RSI dekat overbought" in full_text

    # 4. Verify Compact Format matches BLUEPRINT.md line 234
    compact_text = format_ticket_compact(ticket)
    assert compact_text == "BUY XAUUSD 2651 SL 2636.5 TP 2665.5/2680 0.06lot"


def test_lot_size_floor_and_min_lot_warning() -> None:
    """Test lot sizing calculation floor down and minimum lot risk warning."""
    # Normal case: balance 10,000, 1% risk ($100), SL dist 14.5, contract 100 -> 0.06 lot
    res = calculate_lot_size(
        balance=10000.0,
        risk_pct=1.0,
        contract_size=100.0,
        min_lot=0.01,
        lot_step=0.01,
        entry=2651.0,
        sl=2636.5,
    )
    assert res.lot == 0.06
    assert res.actual_risk_usd == 87.0
    assert res.min_lot_warning is False

    # Small account warning case: balance $500, allowed risk $5 (1%)
    # sl_dist = 14.5 * 100 = $1450 per lot
    # raw_lot = 5 / 1450 = 0.00344 < min_lot 0.01
    res_small = calculate_lot_size(
        balance=500.0,
        risk_pct=1.0,
        contract_size=100.0,
        min_lot=0.01,
        lot_step=0.01,
        entry=2651.0,
        sl=2636.5,
    )
    assert res_small.lot == 0.01
    assert res_small.min_lot_warning is True
    assert res_small.actual_risk_usd == 14.50
    assert res_small.actual_risk_pct == 2.90  # 2.9% > 1.0%
    assert "Risiko aktual 2.90% > batas 1.00%" in (res_small.warning_message or "")


def test_broker_offset_calibration_and_expiration() -> None:
    """Test applying broker offset (+1.3) and checking expiration."""
    now = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
    cal = BrokerCalibration(
        symbol="XAUUSD",
        broker_profile="Exness Standard",
        broker_price=2652.3,
        source_price=2651.0,
        offset=1.3,
        created_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    assert cal.offset == 1.3
    assert not cal.is_expired

    ticket = create_trade_ticket(
        symbol="XAUUSD",
        side="LONG",
        entry_price=2651.0,
        atr14=10.0,
        score=60.0,
        bar_time=now,
    )
    assert ticket.entry == 2651.0

    # Apply offset +1.3
    adj_ticket = apply_broker_offset(ticket, offset=1.3)
    assert adj_ticket.entry == 2652.3
    assert adj_ticket.sl == round_to_tick(ticket.sl + 1.3, 0.1)
    assert adj_ticket.tp1 == round_to_tick(ticket.tp1 + 1.3, 0.1)
    assert adj_ticket.tp2 == round_to_tick(ticket.tp2 + 1.3, 0.1)

    formatted = format_ticket_full(adj_ticket, broker_offset=1.3)
    assert "disesuaikan untuk broker +1,3" in formatted


def test_ticket_expiration_scenarios() -> None:
    """Test ticket invalidation/expiration via time, chase limit, and SL touch."""
    now = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
    ticket = create_trade_ticket(
        symbol="BTCUSDT",
        side="LONG",
        entry_price=65000.0,
        atr14=200.0,
        bar_time=now,
    )
    # Entry zone: 64980 - 65020 (atr 200 * 0.1 = 20)
    # SL: 65000 - 1.5 * 200 = 64700

    # 1. Normal active price
    exp, reason = check_ticket_expiration(
        ticket, current_time=now + timedelta(minutes=15), current_price=65010.0
    )
    assert not exp

    # 2. Time expired after 3 bars (45 min)
    exp, reason = check_ticket_expiration(
        ticket, current_time=now + timedelta(minutes=46), current_price=65010.0
    )
    assert exp
    assert reason == "EXPIRED_TIME"

    # 3. Chase limit: price ran away in profit direction > 0.5 * ATR (65020 + 100 = 65120)
    exp, reason = check_ticket_expiration(
        ticket, current_time=now + timedelta(minutes=10), current_price=65150.0
    )
    assert exp
    assert reason == "CHASE_LIMIT"

    # 4. SL touched before entry
    exp, reason = check_ticket_expiration(
        ticket, current_time=now + timedelta(minutes=10), current_price=64650.0
    )
    assert exp
    assert reason == "SL_HIT_BEFORE_ENTRY"
