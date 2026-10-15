"""Bollinger Bands indicator with squeeze detection and breakout / trend bounce triggers."""

import numpy as np
import pandas as pd

from traderadar.engine.indicators.base import IndicatorResult, MarketContext


def calculate_bollinger_series(
    df: pd.DataFrame,
    period: int = 20,
    std_mult: float = 2.0,
    squeeze_lookback: int = 120,
    squeeze_pct: float = 20.0,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    """Calculate Bollinger Bands, %B, Bandwidth, and Squeeze indicator series.

    Returns:
        (mid, upper, lower, percent_b, bandwidth, is_squeeze)
    """
    if len(df) == 0:
        empty = pd.Series(dtype=float)
        return empty, empty, empty, empty, empty, empty

    close = df["close"]
    mid = close.rolling(window=period).mean()
    # Population standard deviation ddof=0 matching standard TradingView ta.stdev
    std = close.rolling(window=period).std(ddof=0)

    upper = mid + std_mult * std
    lower = mid - std_mult * std

    band_width_diff = upper - lower
    percent_b = ((close - lower) / band_width_diff.replace(0, np.nan)).fillna(0.5)
    bandwidth = (band_width_diff / mid.replace(0, np.nan)).fillna(0.0)

    # Squeeze: bandwidth <= 20th percentile over squeeze_lookback bars
    bw_percentile = bandwidth.rolling(window=squeeze_lookback, min_periods=period).apply(
        lambda s: float(np.percentile(s, squeeze_pct)), raw=True
    )
    is_squeeze = (bandwidth <= bw_percentile).astype(float)

    return mid, upper, lower, percent_b, bandwidth, is_squeeze


class BollingerBandsIndicator:
    """Evaluates Bollinger Bands breakout from squeeze or trend bounce."""

    def __init__(
        self,
        period: int = 20,
        std: float = 2.0,
        squeeze_pct: float = 20.0,
        squeeze_lookback: int = 120,
    ) -> None:
        self.period = period
        self.std = std
        self.squeeze_pct = squeeze_pct
        self.squeeze_lookback = squeeze_lookback

    def evaluate(
        self,
        df: pd.DataFrame,
        context: MarketContext | None = None,
    ) -> IndicatorResult:
        n = len(df)
        if n < self.period:
            return IndicatorResult(
                key="bollinger",
                category="momentum",
                state="NEUTRAL",
                strength=0.0,
                values={},
                reason="Data candle tidak cukup untuk menghitung Bollinger Bands.",
            )

        mid_s, up_s, dn_s, pb_s, bw_s, sq_s = calculate_bollinger_series(
            df,
            period=self.period,
            std_mult=self.std,
            squeeze_lookback=self.squeeze_lookback,
            squeeze_pct=self.squeeze_pct,
        )

        last_mid = float(mid_s.iloc[-1])
        last_up = float(up_s.iloc[-1])
        last_dn = float(dn_s.iloc[-1])
        last_pb = float(pb_s.iloc[-1])
        last_bw = float(bw_s.iloc[-1])
        last_squeeze = bool(sq_s.iloc[-1] == 1.0)
        last_close = float(df["close"].iloc[-1])

        # Check if previous bar was in squeeze
        prev_squeeze = bool(sq_s.iloc[-2] == 1.0) if n >= 2 else False
        recent_squeeze = bool(sq_s.iloc[-4:-1].sum() >= 1) if n >= 4 else False

        # Check %B bounce in recent 3 bars:
        # Bull bounce: was < 0.2, now > 0.3
        # Bear bounce: was > 0.8, now < 0.7
        pb_vals = pb_s.iloc[-4:].values if n >= 4 else pb_s.values
        rebounded_bull = (
            np.min(pb_vals[:-1]) < 0.2 and last_pb > 0.3 if len(pb_vals) >= 2 else False
        )
        rebounded_bear = (
            np.max(pb_vals[:-1]) > 0.8 and last_pb < 0.7 if len(pb_vals) >= 2 else False
        )

        htf_trend = context.htf_trend if context else None

        values = {
            "mid": round(last_mid, 4),
            "upper": round(last_up, 4),
            "lower": round(last_dn, 4),
            "percent_b": round(last_pb, 4),
            "bandwidth": round(last_bw, 6),
            "is_squeeze": 1.0 if last_squeeze else 0.0,
        }

        # Case 1: Breakout out of squeeze
        if (prev_squeeze or recent_squeeze) and last_close > last_up:
            return IndicatorResult(
                key="bollinger",
                category="momentum",
                state="BULL",
                strength=0.8,
                values=values,
                reason="Breakout bullish kuat keluar dari zona squeeze Bollinger Bands.",
            )
        if (prev_squeeze or recent_squeeze) and last_close < last_dn:
            return IndicatorResult(
                key="bollinger",
                category="momentum",
                state="BEAR",
                strength=0.8,
                values=values,
                reason="Breakdown bearish kuat keluar dari zona squeeze Bollinger Bands.",
            )

        # Case 2: In squeeze currently -> NEUTRAL (volatilitas menyempit, tunggu breakout)
        if last_squeeze:
            return IndicatorResult(
                key="bollinger",
                category="momentum",
                state="NEUTRAL",
                strength=0.0,
                values=values,
                reason="Volatilitas menyempit (squeeze), bersiap untuk breakout.",
            )

        # Case 3: Trend bounce
        if (htf_trend == "BULL" or htf_trend is None) and rebounded_bull:
            return IndicatorResult(
                key="bollinger",
                category="momentum",
                state="BULL",
                strength=0.5,
                values=values,
                reason="Harga memantul dari lower band (%B naik dari <0.2 ke >0.3).",
            )
        if (htf_trend == "BEAR" or htf_trend is None) and rebounded_bear:
            return IndicatorResult(
                key="bollinger",
                category="momentum",
                state="BEAR",
                strength=0.5,
                values=values,
                reason="Harga memantul turun dari upper band (%B turun dari >0.8 ke <0.7).",
            )

        # Default Neutral
        return IndicatorResult(
            key="bollinger",
            category="momentum",
            state="NEUTRAL",
            strength=0.0,
            values=values,
            reason=f"Harga dalam band (%B={last_pb:.2f}), tanpa sinyal breakout atau pantulan.",
        )
