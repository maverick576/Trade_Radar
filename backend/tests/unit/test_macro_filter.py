"""Unit tests for Macro Filter checks (M1-M8)."""

from datetime import UTC, datetime

from traderadar.engine.macro_filter import MacroFilterContext, evaluate_macro_filters


def test_macro_m1_htf_trend() -> None:
    """M1 fails only if BOTH H4 (< EMA200) and D1 (ST BEAR) oppose a LONG signal."""
    # Case 1: H4 opposes (< EMA200) AND D1 opposes (dir < 0) => M1 FAILS
    ctx_both_oppose = MacroFilterContext(
        symbol="BTCUSDT",
        side="LONG",
        bar_time=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
        h4_close=60000.0,
        h4_ema200=62000.0,  # Below EMA200
        d1_supertrend_dir=-1.0,  # D1 Bear
    )
    res1 = evaluate_macro_filters(ctx_both_oppose)
    assert not res1.passed
    assert "M1" in res1.blocked_by

    # Case 2: H4 opposes (< EMA200) BUT D1 supports (dir > 0) => M1 PASSES
    ctx_d1_supports = MacroFilterContext(
        symbol="BTCUSDT",
        side="LONG",
        bar_time=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
        h4_close=60000.0,
        h4_ema200=62000.0,
        d1_supertrend_dir=1.0,  # D1 Bull supports!
    )
    res2 = evaluate_macro_filters(ctx_d1_supports)
    assert "M1" not in res2.blocked_by


def test_macro_m2_news_blackout() -> None:
    """M2 fails if there is a high impact news event within ±30 minutes."""
    ctx_news = MacroFilterContext(
        symbol="BTCUSDT",
        side="LONG",
        bar_time=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
        has_news_event_nearby=True,
        nearby_news_detail="CPI USD release in 10m",
    )
    res = evaluate_macro_filters(ctx_news)
    assert not res.passed
    assert "M2" in res.blocked_by


def test_macro_m3_volatility_atr() -> None:
    """M3 fails if ATR < P10 (market dead) or ATR > P95 (extreme)."""
    # Low ATR < P10
    ctx_dead = MacroFilterContext(
        symbol="BTCUSDT",
        side="LONG",
        bar_time=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
        current_atr=50.0,
        atr_p10=100.0,
        atr_p95=500.0,
    )
    res = evaluate_macro_filters(ctx_dead)
    assert not res.passed
    assert "M3" in res.blocked_by

    # Extreme ATR > P95
    ctx_wild = MacroFilterContext(
        symbol="BTCUSDT",
        side="LONG",
        bar_time=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
        current_atr=600.0,
        atr_p10=100.0,
        atr_p95=500.0,
    )
    assert "M3" in evaluate_macro_filters(ctx_wild).blocked_by


def test_macro_m4_gold_session() -> None:
    """M4 checks FX gold market hours and rollover window for Gold, passes for Crypto."""
    # Crypto passes unconditionally
    ctx_crypto = MacroFilterContext(
        symbol="BTCUSDT",
        side="LONG",
        bar_time=datetime(2026, 10, 17, 12, 0, tzinfo=UTC),  # Saturday
        is_gold=False,
    )
    assert "M4" not in evaluate_macro_filters(ctx_crypto).blocked_by

    # Gold on Saturday is closed
    ctx_gold_sat = MacroFilterContext(
        symbol="XAUUSD",
        side="LONG",
        bar_time=datetime(2026, 10, 17, 12, 0, tzinfo=UTC),  # Saturday
        is_gold=True,
    )
    res_gold = evaluate_macro_filters(ctx_gold_sat)
    assert not res_gold.passed
    assert "M4" in res_gold.blocked_by

    # Gold during rollover (21:00 UTC on Tuesday)
    ctx_gold_roll = MacroFilterContext(
        symbol="XAUUSD",
        side="LONG",
        bar_time=datetime(2026, 10, 13, 21, 0, tzinfo=UTC),  # Tuesday 21:00 UTC
        is_gold=True,
    )
    assert "M4" in evaluate_macro_filters(ctx_gold_roll).blocked_by


def test_macro_m5_liquidity_spread() -> None:
    """M5 fails if current spread > 2x median spread."""
    ctx_thin = MacroFilterContext(
        symbol="BTCUSDT",
        side="LONG",
        bar_time=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
        current_spread=5.0,
        median_spread_24h=1.0,  # 5 > 2*1
    )
    assert "M5" in evaluate_macro_filters(ctx_thin).blocked_by


def test_macro_m6_data_freshness() -> None:
    """M6 fails if candle age > 2x TF or WS disconnected."""
    ctx_stale = MacroFilterContext(
        symbol="BTCUSDT",
        side="LONG",
        bar_time=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
        candle_age_seconds=2000.0,  # > 2 * 900
        tf_seconds=900.0,
    )
    assert "M6" in evaluate_macro_filters(ctx_stale).blocked_by

    ctx_ws_down = MacroFilterContext(
        symbol="BTCUSDT",
        side="LONG",
        bar_time=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
        ws_connected=False,
    )
    assert "M6" in evaluate_macro_filters(ctx_ws_down).blocked_by


def test_macro_m7_funding_rate() -> None:
    """M7 fails if absolute funding rate > 0.1% (0.001)."""
    ctx_extreme_funding = MacroFilterContext(
        symbol="BTCUSDT",
        side="LONG",
        bar_time=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
        funding_rate=0.0015,  # 0.15% > 0.10%
    )
    assert "M7" in evaluate_macro_filters(ctx_extreme_funding).blocked_by


def test_macro_m8_risk_paper() -> None:
    """M8 fails if daily loss limit hit or position already open."""
    ctx_loss = MacroFilterContext(
        symbol="BTCUSDT",
        side="LONG",
        bar_time=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
        daily_loss_limit_reached=True,
    )
    assert "M8" in evaluate_macro_filters(ctx_loss).blocked_by

    ctx_pos = MacroFilterContext(
        symbol="BTCUSDT",
        side="LONG",
        bar_time=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
        has_open_position_for_symbol=True,
    )
    assert "M8" in evaluate_macro_filters(ctx_pos).blocked_by
