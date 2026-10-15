"""EMA Ribbon indicator with 5 exponential moving averages and ATR volatility scaling."""

import numpy as np
import pandas as pd

from traderadar.engine.indicators.base import IndicatorResult, MarketContext


def calculate_atr_series(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Wilder's Average True Range (matching TradingView ta.atr)."""
    if len(df) == 0:
        return pd.Series(dtype=float)

    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    # Wilder's RMA uses alpha = 1 / period
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    return atr


def calculate_ema_ribbon_series(
    df: pd.DataFrame,
    periods: list[int] | None = None,
) -> dict[int, pd.Series]:
    """Calculate EMAs for specified ribbon periods (default: [8, 13, 21, 34, 55])."""
    if periods is None:
        periods = [8, 13, 21, 34, 55]

    close = df["close"]
    emas: dict[int, pd.Series] = {}
    for p in periods:
        # TradingView ta.ema uses span=p with adjust=False
        emas[p] = close.ewm(span=p, adjust=False).mean()
    return emas


class EmaRibbonIndicator:
    """Evaluates EMA Ribbon alignment and volatility-adjusted expansion."""

    def __init__(self, periods: list[int] | None = None) -> None:
        self.periods = periods or [8, 13, 21, 34, 55]

    def evaluate(
        self,
        df: pd.DataFrame,
        context: MarketContext | None = None,
    ) -> IndicatorResult:
        if len(df) < max(self.periods):
            return IndicatorResult(
                key="ema_ribbon",
                category="trend",
                state="NEUTRAL",
                strength=0.0,
                values={},
                reason="Data candle tidak cukup untuk menghitung EMA Ribbon.",
            )

        emas = calculate_ema_ribbon_series(df, self.periods)
        atr_series = calculate_atr_series(df, period=14)

        last_close = float(df["close"].iloc[-1])
        last_atr = max(float(atr_series.iloc[-1]), 1e-6)

        p8, p13, p21, p34, p55 = self.periods
        e8 = float(emas[p8].iloc[-1])
        e13 = float(emas[p13].iloc[-1])
        e21 = float(emas[p21].iloc[-1])
        e34 = float(emas[p34].iloc[-1])
        e55 = float(emas[p55].iloc[-1])

        # Check adjacent pairs alignment: (8 vs 13), (13 vs 21), (21 vs 34), (34 vs 55)
        bull_pairs = sum(
            [
                e8 > e13,
                e13 > e21,
                e21 > e34,
                e34 > e55,
            ]
        )
        bear_pairs = sum(
            [
                e8 < e13,
                e13 < e21,
                e21 < e34,
                e34 < e55,
            ]
        )

        spread = e8 - e55
        spread_atr = spread / last_atr

        values = {
            "ema8": round(e8, 4),
            "ema13": round(e13, 4),
            "ema21": round(e21, 4),
            "ema34": round(e34, 4),
            "ema55": round(e55, 4),
            "spread": round(spread, 4),
            "spread_atr": round(spread_atr, 4),
            "atr14": round(last_atr, 4),
        }

        # Perfect bullish alignment: 8>13>21>34>55 and close > EMA8
        if bull_pairs == 4 and last_close > e8:
            state = "BULL"
            strength = float(np.clip(spread / (2.0 * last_atr), 0.0, 1.0))
            reason = (
                f"Ribbon tersusun naik sempurna, harga di atas EMA8 (lebar {spread_atr:.1f}x ATR)."
            )
        # Perfect bearish alignment: 8<13<21<34<55 and close < EMA8
        elif bear_pairs == 4 and last_close < e8:
            state = "BEAR"
            strength = float(np.clip((-spread) / (2.0 * last_atr), 0.0, 1.0))
            reason = (
                f"Ribbon turun sempurna, harga di bawah EMA8 (lebar {-spread_atr:.1f}x ATR)."
            )
        # Partial bullish alignment (all 4 consecutive pairs ordered, close inside)
        elif bull_pairs >= 4:
            state = "BULL"
            strength = 0.5
            reason = "Ribbon tersusun naik, harga terkonsolidasi di dalam ribbon."
        # Partial bearish alignment
        elif bear_pairs >= 4:
            state = "BEAR"
            strength = 0.5
            reason = "Ribbon tersusun turun, harga terkonsolidasi di dalam ribbon."
        else:
            state = "NEUTRAL"
            strength = 0.0
            reason = "EMA ribbon saling berpotongan atau berkontraksi (sideways)."

        return IndicatorResult(
            key="ema_ribbon",
            category="trend",
            state=state,
            strength=round(strength, 4),
            values=values,
            reason=reason,
        )
