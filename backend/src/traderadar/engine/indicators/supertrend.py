"""Supertrend indicator with Wilder ATR, direction flip detection, and distance filtering."""

import numpy as np
import pandas as pd

from traderadar.engine.indicators.base import IndicatorResult, MarketContext
from traderadar.engine.indicators.ema_ribbon import calculate_atr_series


def calculate_supertrend_series(
    df: pd.DataFrame,
    atr_period: int = 10,
    multiplier: float = 3.0,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Calculate Supertrend matching TradingView's exact formulation.

    Returns:
        (supertrend, direction, atr, bars_since_flip)
        direction: 1.0 for Bullish (price above line), -1.0 for Bearish (price below line)
    """
    n = len(df)
    if n == 0:
        empty = pd.Series(dtype=float)
        return empty, empty, empty, empty

    atr = calculate_atr_series(df, period=atr_period).values
    hl2 = ((df["high"] + df["low"]) / 2.0).values
    close = df["close"].values

    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    final_upper = np.zeros(n)
    final_lower = np.zeros(n)
    trend = np.ones(n)  # 1 for bull, -1 for bear
    supertrend = np.zeros(n)
    bars_since_flip = np.zeros(n)

    # Initialize first bar
    final_upper[0] = basic_upper[0]
    final_lower[0] = basic_lower[0]
    trend[0] = 1.0 if close[0] >= basic_lower[0] else -1.0
    supertrend[0] = final_lower[0] if trend[0] == 1.0 else final_upper[0]
    flip_counter = 0

    for i in range(1, n):
        # Final Upper Band
        if basic_upper[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i - 1]

        # Final Lower Band
        if basic_lower[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i - 1]

        # Trend & Supertrend
        prev_trend = trend[i - 1]
        if prev_trend == 1.0:
            if close[i] < final_lower[i]:
                trend[i] = -1.0
                supertrend[i] = final_upper[i]
                flip_counter = 0
            else:
                trend[i] = 1.0
                supertrend[i] = final_lower[i]
                flip_counter += 1
        else:
            if close[i] > final_upper[i]:
                trend[i] = 1.0
                supertrend[i] = final_lower[i]
                flip_counter = 0
            else:
                trend[i] = -1.0
                supertrend[i] = final_upper[i]
                flip_counter += 1

        bars_since_flip[i] = flip_counter

    idx = df.index
    return (
        pd.Series(supertrend, index=idx),
        pd.Series(trend, index=idx),
        pd.Series(atr, index=idx),
        pd.Series(bars_since_flip, index=idx),
    )


class SupertrendIndicator:
    """Evaluates Supertrend line, direction, recent flips, and proximity to price."""

    def __init__(
        self,
        atr_period: int = 10,
        multiplier: float = 3.0,
        recent_flip_bars: int = 3,
    ) -> None:
        self.atr_period = atr_period
        self.multiplier = multiplier
        self.recent_flip_bars = recent_flip_bars

    def evaluate(
        self,
        df: pd.DataFrame,
        context: MarketContext | None = None,
    ) -> IndicatorResult:
        if len(df) < self.atr_period + 1:
            return IndicatorResult(
                key="supertrend",
                category="trend",
                state="NEUTRAL",
                strength=0.0,
                values={},
                reason="Data candle tidak cukup untuk menghitung Supertrend.",
            )

        st, direction, atr, flips = calculate_supertrend_series(
            df,
            atr_period=self.atr_period,
            multiplier=self.multiplier,
        )

        last_st = float(st.iloc[-1])
        last_dir = float(direction.iloc[-1])
        last_atr = max(float(atr.iloc[-1]), 1e-6)
        last_flips = int(flips.iloc[-1])
        last_close = float(df["close"].iloc[-1])

        distance = abs(last_close - last_st)
        distance_atr = distance / last_atr

        state = "BULL" if last_dir == 1.0 else "BEAR"

        # Base strength: 0.6 + 0.4 if flip occurred within recent_flip_bars
        if last_flips <= self.recent_flip_bars:
            strength = 1.0
            flip_note = f"flip baru {last_flips} bar lalu"
        else:
            strength = 0.6
            flip_note = f"tren bertahan {last_flips} bar"

        # If price distance to line < 0.3 ATR -> reduce strength by 0.5 (easily pierced)
        is_close_to_line = distance < 0.3 * last_atr
        if is_close_to_line:
            strength *= 0.5

        values = {
            "supertrend": round(last_st, 4),
            "direction": last_dir,
            "atr": round(last_atr, 4),
            "distance": round(distance, 4),
            "distance_atr": round(distance_atr, 4),
            "bars_since_flip": float(last_flips),
        }

        if state == "BULL":
            if is_close_to_line:
                reason = f"Supertrend bull {last_st:.2f}, harga dekat ({distance_atr:.1f}x ATR)."
            else:
                reason = f"Supertrend bullish di {last_st:.2f} ({flip_note})."
        else:
            if is_close_to_line:
                reason = f"Supertrend bear {last_st:.2f}, harga dekat ({distance_atr:.1f}x ATR)."
            else:
                reason = f"Supertrend bearish di {last_st:.2f} ({flip_note})."

        return IndicatorResult(
            key="supertrend",
            category="trend",
            state=state,
            strength=round(strength, 4),
            values=values,
            reason=reason,
        )
