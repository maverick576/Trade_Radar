"""RSI indicator with Wilder smoothing, zero-lookahead pivot divergence, and momentum crosses."""

import numpy as np
import pandas as pd

from traderadar.engine.indicators.base import IndicatorResult, MarketContext


def calculate_rsi_series(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Wilder's Relative Strength Index matching TradingView ta.rsi."""
    if len(df) == 0:
        return pd.Series(dtype=float)

    delta = df["close"].diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    # Wilder's RMA: alpha = 1 / period
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()

    # Avoid zero division
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    # Where avg_loss was 0, RSI is 100
    rsi = rsi.fillna(100.0)
    return rsi


class RsiDivergenceIndicator:
    """Evaluates RSI-14, zero-lookahead regular divergences, and 50-level crosses."""

    def __init__(
        self,
        period: int = 14,
        pivot_left: int = 5,
        pivot_right: int = 3,
        min_gap: int = 5,
        max_gap: int = 60,
        valid_bars: int = 10,
    ) -> None:
        self.period = period
        self.pivot_left = pivot_left
        self.pivot_right = pivot_right
        self.min_gap = min_gap
        self.max_gap = max_gap
        self.valid_bars = valid_bars

    def evaluate(
        self,
        df: pd.DataFrame,
        context: MarketContext | None = None,
    ) -> IndicatorResult:
        n = len(df)
        if n < self.period + self.pivot_left + self.pivot_right:
            return IndicatorResult(
                key="rsi_div",
                category="momentum",
                state="NEUTRAL",
                strength=0.0,
                values={},
                reason="Data candle tidak cukup untuk menghitung RSI Divergence.",
            )

        rsi_series = calculate_rsi_series(df, period=self.period)
        rsi_vals = rsi_series.values
        low_vals = df["low"].values
        high_vals = df["high"].values
        t = n - 1
        current_rsi = float(rsi_vals[-1])

        # Anti-lookahead pivot scanning:
        # A pivot at index i requires i - left >= 0 and i + right <= t.
        # Max candidate i is t - pivot_right.
        max_candidate_i = t - self.pivot_right

        # Find confirmed low pivots
        low_pivots: list[tuple[int, float, float]] = []  # (index, price_low, rsi)
        # Find confirmed high pivots
        high_pivots: list[tuple[int, float, float]] = []  # (index, price_high, rsi)

        for i in range(self.pivot_left, max_candidate_i + 1):
            # Check pivot low
            window_low = low_vals[i - self.pivot_left : i + self.pivot_right + 1]
            if low_vals[i] == np.min(window_low) and np.sum(window_low == low_vals[i]) == 1:
                low_pivots.append((i, float(low_vals[i]), float(rsi_vals[i])))

            # Check pivot high
            window_high = high_vals[i - self.pivot_left : i + self.pivot_right + 1]
            if high_vals[i] == np.max(window_high) and np.sum(window_high == high_vals[i]) == 1:
                high_pivots.append((i, float(high_vals[i]), float(rsi_vals[i])))

        # Check Bullish Regular Divergence
        # Lower low in price, higher low in RSI, recent pivot RSI < 40
        bull_div = False
        bull_div_detail = ""
        if len(low_pivots) >= 2:
            i2, p2, r2 = low_pivots[-1]
            i1, p1, r1 = low_pivots[-2]
            bars_since_confirm = t - (i2 + self.pivot_right)
            gap = i2 - i1
            if (
                self.min_gap <= gap <= self.max_gap
                and bars_since_confirm <= self.valid_bars
                and p2 < p1
                and r2 > r1
                and r2 < 40.0
            ):
                bull_div = True
                bull_div_detail = (
                    f"Bullish divergence (p={p2:.2f}<{p1:.2f}, RSI={r2:.1f}>{r1:.1f} < 40)"
                )

        # Check Bearish Regular Divergence
        # Higher high in price, lower high in RSI, recent pivot RSI > 60
        bear_div = False
        bear_div_detail = ""
        if len(high_pivots) >= 2:
            i2, p2, r2 = high_pivots[-1]
            i1, p1, r1 = high_pivots[-2]
            bars_since_confirm = t - (i2 + self.pivot_right)
            gap = i2 - i1
            if (
                self.min_gap <= gap <= self.max_gap
                and bars_since_confirm <= self.valid_bars
                and p2 > p1
                and r2 < r1
                and r2 > 60.0
            ):
                bear_div = True
                bear_div_detail = (
                    f"Bearish divergence (p={p2:.2f}>{p1:.2f}, RSI={r2:.1f}<{r1:.1f} > 60)"
                )

        # Non-divergence checks: RSI crossed 50 within last 3 bars
        # Check cross above 50: rsi[t-k-1] < 50 <= rsi[t-k]
        crossed_up_50 = False
        crossed_down_50 = False
        bars_since_cross = 999

        for k in range(min(3, n - 2)):
            idx_cur = t - k
            idx_prev = idx_cur - 1
            if rsi_vals[idx_prev] < 50.0 and rsi_vals[idx_cur] >= 50.0:
                crossed_up_50 = True
                bars_since_cross = min(bars_since_cross, k)
            if rsi_vals[idx_prev] > 50.0 and rsi_vals[idx_cur] <= 50.0:
                crossed_down_50 = True
                bars_since_cross = min(bars_since_cross, k)

        values = {
            "rsi": round(current_rsi, 2),
            "bull_div": 1.0 if bull_div else 0.0,
            "bear_div": 1.0 if bear_div else 0.0,
            "bars_since_cross50": float(bars_since_cross) if bars_since_cross < 999 else -1.0,
        }

        # Priority 1: Divergence
        if bull_div:
            return IndicatorResult(
                key="rsi_div",
                category="momentum",
                state="BULL",
                strength=0.9,
                values=values,
                reason=bull_div_detail,
            )
        if bear_div:
            return IndicatorResult(
                key="rsi_div",
                category="momentum",
                state="BEAR",
                strength=0.9,
                values=values,
                reason=bear_div_detail,
            )

        # Priority 2: 50 Cross within 3 bars
        if crossed_up_50 and current_rsi < 70.0:
            return IndicatorResult(
                key="rsi_div",
                category="momentum",
                state="BULL",
                strength=0.6,
                values=values,
                reason=(
                    f"RSI melintasi naik level 50 ({current_rsi:.1f}) konfirmasi momentum bullish."
                ),
            )
        if crossed_down_50 and current_rsi > 30.0:
            return IndicatorResult(
                key="rsi_div",
                category="momentum",
                state="BEAR",
                strength=0.6,
                values=values,
                reason=(
                    f"RSI melintasi turun level 50 ({current_rsi:.1f}) konfirmasi momentum bearish."
                ),
            )

        # Priority 3: Extremes
        if current_rsi > 75.0:
            return IndicatorResult(
                key="rsi_div",
                category="momentum",
                state="BEAR",
                strength=0.3,
                values=values,
                reason=f"RSI jenuh beli ({current_rsi:.1f} > 75), potensi koreksi.",
            )
        if current_rsi < 25.0:
            return IndicatorResult(
                key="rsi_div",
                category="momentum",
                state="BULL",
                strength=0.3,
                values=values,
                reason=f"RSI jenuh jual ({current_rsi:.1f} < 25), potensi rebound.",
            )

        return IndicatorResult(
            key="rsi_div",
            category="momentum",
            state="NEUTRAL",
            strength=0.0,
            values=values,
            reason=f"RSI berada di zona netral ({current_rsi:.1f}) tanpa divergensi aktif.",
        )
