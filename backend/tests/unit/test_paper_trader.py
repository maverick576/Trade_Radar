"""Unit tests for Paper Trading simulation engine.

Tests:
- Position sizing: (equity * risk_pct) / R
- Entry with taker slippage (2 bps) and taker fee (0.05%)
- Invariant: SL & TP reached in the same candle -> SL hit first!
- TP1 (+1R) closes 50% & moves SL to BE
- TP2 (+2R) closes remainder
- Time stop after 32 bars
- Opposite signal exit
- Daily loss limit (3% daily loss limit)
- Virtual trade simulation for blocked signals
"""

from datetime import UTC, datetime, timedelta

from traderadar.engine.paper import (
    CandleBar,
    PaperTradeState,
    calculate_paper_entry_price,
    check_daily_loss_limit,
    close_paper_trade_opposite,
    create_paper_position,
    update_paper_position_with_bar,
)


def test_paper_position_creation_and_sizing() -> None:
    """Verify position sizing and entry execution price with taker slippage and fees."""
    # Equity = $1000, risk 1% = $10. Entry 2651, SL 2636.5 (R = 14.5)
    # Expected size = $10 / 14.5 = 0.689655 units
    now = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)

    # Slippage: 2 bps = 0.02%
    # Long open 2651.0 -> 2651 * (1 + 0.0002) = 2651.5302
    expected_entry = calculate_paper_entry_price(2651.0, "LONG", slippage_bps=2)
    assert round(expected_entry, 2) == 2651.53

    pos = create_paper_position(
        symbol="XAUUSD",
        side="LONG",
        bar_open=2651.0,
        bar_time=now,
        sl=2636.5,
        tp1=2665.5,
        tp2=2680.0,
        equity=1000.0,
        risk_pct=1.0,
        slippage_bps=2,
    )

    assert pos.status == "OPEN"
    assert pos.side == "LONG"
    assert pos.bars_held == 0
    assert pos.tp1_hit is False
    assert pos.entry_price == 2651.5302
    assert pos.fees_usd > 0  # Entry fee paid
    assert pos.is_virtual is False


def test_tp1_to_be_to_tp2_progression() -> None:
    """Test full profit lifecycle: Bar 1 hits TP1 (close 50%, SL->BE), Bar 2 hits TP2."""
    now = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
    pos = create_paper_position(
        symbol="ETHUSDT",
        side="LONG",
        bar_open=3000.0,
        bar_time=now,
        sl=2950.0,  # R = ~50
        tp1=3050.0,
        tp2=3100.0,
        equity=1000.0,
        risk_pct=1.0,
        slippage_bps=0,  # zero slippage for exact math
    )
    assert pos.entry_price == 3000.0
    assert pos.current_sl == 2950.0

    # Bar 1: Price reaches 3060 (hits TP1, does not hit TP2)
    bar1 = CandleBar(
        open_time=now + timedelta(minutes=15),
        open=3005.0,
        high=3065.0,
        low=2990.0,
        close=3040.0,
    )
    pos = update_paper_position_with_bar(pos, bar1)
    assert pos.status == "OPEN"
    assert pos.tp1_hit is True
    assert pos.current_sl == 3000.0  # SL moved to BE!
    assert pos.bars_held == 1

    # Bar 2: Price hits TP2 at 3105
    bar2 = CandleBar(
        open_time=now + timedelta(minutes=30),
        open=3045.0,
        high=3110.0,
        low=3030.0,
        close=3095.0,
    )
    pos = update_paper_position_with_bar(pos, bar2)
    assert pos.status == "CLOSED"
    assert pos.exit_reason == "TP2"
    assert pos.exit_price == 3100.0
    # TP1 (+1R) 50% + TP2 (+2R) 50% = +1.5R realized
    assert pos.pnl_r == 1.5
    assert (pos.pnl_usd or 0.0) > 0.0


def test_same_candle_sl_priority_over_tp() -> None:
    """Invariant test: If both SL and TP are hit in the exact same candle, SL executes first!"""
    now = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
    pos = create_paper_position(
        symbol="BTCUSDT",
        side="LONG",
        bar_open=65000.0,
        bar_time=now,
        sl=64500.0,  # SL
        tp1=65500.0,  # TP1
        tp2=66000.0,
        equity=1000.0,
        risk_pct=1.0,
        slippage_bps=0,
    )

    # Wild candle: Low reaches 64400 (SL hit) AND High reaches 65600 (TP1 hit)
    wild_bar = CandleBar(
        open_time=now + timedelta(minutes=15),
        open=65000.0,
        high=65600.0,
        low=64400.0,
        close=64800.0,
    )
    res = update_paper_position_with_bar(pos, wild_bar)

    assert res.status == "CLOSED"
    assert res.exit_reason == "SL"  # SL must take priority!
    assert res.exit_price == 64500.0
    assert (res.pnl_r or 0.0) < 0.0


def test_time_stop_after_32_bars() -> None:
    """Test position exit via time stop after 32 bars held."""
    now = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
    pos = create_paper_position(
        symbol="SOLUSDT",
        side="SHORT",
        bar_open=150.0,
        bar_time=now,
        sl=155.0,
        tp1=145.0,
        tp2=140.0,
        slippage_bps=0,
    )

    # Advance 31 sideways bars
    for i in range(1, 32):
        bar = CandleBar(
            open_time=now + timedelta(minutes=15 * i),
            open=149.5,
            high=151.0,
            low=148.0,
            close=149.0,
        )
        pos = update_paper_position_with_bar(pos, bar, time_stop_bars=32)
        assert pos.status == "OPEN"
        assert pos.bars_held == i

    # Bar 32: should trigger time stop
    bar32 = CandleBar(
        open_time=now + timedelta(minutes=15 * 32),
        open=149.0,
        high=150.5,
        low=148.5,
        close=149.2,
    )
    pos = update_paper_position_with_bar(pos, bar32, time_stop_bars=32)
    assert pos.status == "CLOSED"
    assert pos.exit_reason == "TIME_STOP"
    assert pos.exit_price == 149.2
    assert pos.bars_held == 32


def test_opposite_signal_exit() -> None:
    """Test closing paper position immediately when an opposite STRONG signal is produced."""
    now = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
    pos = create_paper_position(
        symbol="XAUUSD",
        side="LONG",
        bar_open=2650.0,
        bar_time=now,
        sl=2635.0,
        tp1=2665.0,
        tp2=2680.0,
        slippage_bps=0,
    )

    closed = close_paper_trade_opposite(
        trade=pos,
        exit_price=2648.0,
        exit_time=now + timedelta(minutes=30),
    )
    assert closed.status == "CLOSED"
    assert closed.exit_reason == "OPPOSITE_SIGNAL"
    assert closed.exit_price == 2648.0


def test_daily_loss_limit_check() -> None:
    """Test daily loss limit threshold: 3% of initial equity ($30 on $1000)."""
    now = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)

    # 1. Closed trades losing $20 (2% loss -> limit not hit)
    t1 = PaperTradeState(
        symbol="BTCUSDT",
        side="LONG",
        entry_time=now - timedelta(hours=2),
        entry_price=65000.0,
        size=0.1,
        initial_sl=64500.0,
        current_sl=64500.0,
        tp1=65500.0,
        tp2=66000.0,
        r_distance=500.0,
        status="CLOSED",
        exit_time=now - timedelta(hours=1),
        exit_price=64800.0,
        pnl_usd=-20.0,
        pnl_r=-0.4,
        is_virtual=False,
    )
    is_hit, loss = check_daily_loss_limit([t1], initial_equity=1000.0, daily_loss_limit_pct=3.0)
    assert not is_hit
    assert loss == -20.0

    # 2. Second losing trade losing $15 (total $35 loss > 3% -> limit hit)
    t2 = PaperTradeState(
        symbol="ETHUSDT",
        side="SHORT",
        entry_time=now - timedelta(hours=1),
        entry_price=3000.0,
        size=1.0,
        initial_sl=3050.0,
        current_sl=3050.0,
        tp1=2950.0,
        tp2=2900.0,
        r_distance=50.0,
        status="CLOSED",
        exit_time=now,
        exit_price=3015.0,
        pnl_usd=-15.0,
        pnl_r=-0.3,
        is_virtual=False,
    )
    is_hit, loss = check_daily_loss_limit([t1, t2], initial_equity=1000.0, daily_loss_limit_pct=3.0)
    assert is_hit
    assert loss == -35.0


def test_virtual_paper_trade_for_blocked_signals() -> None:
    """Test that blocked signals create simulated virtual trades with is_virtual=True."""
    now = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
    v_pos = create_paper_position(
        symbol="XAUUSD",
        side="LONG",
        bar_open=2650.0,
        bar_time=now,
        sl=2635.0,
        tp1=2665.0,
        tp2=2680.0,
        is_virtual=True,
    )
    assert v_pos.is_virtual is True

    # Virtual trades are ignored by daily loss limit
    v_pos.status = "CLOSED"
    v_pos.pnl_usd = -100.0
    is_hit, loss = check_daily_loss_limit([v_pos], initial_equity=1000.0, daily_loss_limit_pct=3.0)
    assert not is_hit
    assert loss == 0.0
