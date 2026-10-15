"""Unit tests for Strategy B (Triple-EMA)."""

import pandas as pd

from traderadar.engine.macro_filter import MacroFilterResult
from traderadar.engine.strategies.triple_ema import evaluate_triple_ema


def test_triple_ema_bullish_setup() -> None:
    """Construct an uptrend crossover where EMA9 crosses above EMA21(open) above EMA50."""
    # Series with exact crossover on the last bar
    prices = (
        [100.0 + i * 0.5 for i in range(70)]
        + [100.0 + 70 * 0.5 - i * 1.2 for i in range(9)]
        + [131.0]
    )
    n = len(prices)

    df_m15 = pd.DataFrame(
        {
            "open": [p - 0.2 for p in prices],
            "high": [p + 0.5 for p in prices],
            "low": [p - 0.5 for p in prices],
            "close": prices,
            "volume": [100.0] * n,
        }
    )

    # df_h1 strongly bullish
    h1_prices = [100.0 + i * 1.0 for i in range(n)]
    df_h1 = pd.DataFrame(
        {
            "open": h1_prices,
            "high": [p + 1.0 for p in h1_prices],
            "low": [p - 1.0 for p in h1_prices],
            "close": h1_prices,
            "volume": [500.0] * n,
        }
    )

    res = evaluate_triple_ema(df_m15, df_h1)

    assert res.state == "LONG"
    assert res.entry == prices[-1]
    assert res.sl is not None and res.sl < res.entry
    assert res.tp is not None and res.tp > res.entry
    assert res.confirmed is True


def test_triple_ema_blocked_by_macro_filter() -> None:
    """When setup is valid but M2-M6 fails, state remains LONG but confirmed is False."""
    prices = (
        [100.0 + i * 0.5 for i in range(70)]
        + [100.0 + 70 * 0.5 - i * 1.2 for i in range(9)]
        + [131.0]
    )
    n = len(prices)

    df_m15 = pd.DataFrame(
        {
            "open": [p - 0.2 for p in prices],
            "high": [p + 0.5 for p in prices],
            "low": [p - 0.5 for p in prices],
            "close": prices,
            "volume": [100.0] * n,
        }
    )

    from traderadar.engine.macro_filter import MacroCheck

    macro_res = MacroFilterResult(
        passed=False,
        checks=[
            MacroCheck(id="M2", name="News", passed=False, detail="USD High-impact blackout"),
        ],
        blocked_by=["M2"],
    )

    res = evaluate_triple_ema(df_m15, df_h1=None, macro_result=macro_res)

    assert res.state == "LONG"
    assert res.confirmed is False
    assert "M2" in res.reason
