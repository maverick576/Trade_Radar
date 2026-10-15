"""Cumulative Volume Delta (CVD) and OBV indicator with normalized slope regression."""

from typing import Any

import numpy as np
import pandas as pd

from traderadar.engine.indicators.base import IndicatorResult, MarketContext


def calculate_linear_regression_slope(series: pd.Series, window: int = 20) -> pd.Series:
    """Calculate rolling linear regression slope over window length."""
    n = window
    weights = np.arange(n) - (n - 1.0) / 2.0
    denominator = (n * (n**2 - 1.0)) / 12.0

    def get_slope(w: np.ndarray[Any, Any]) -> float:
        return float(np.dot(weights, w) / denominator)

    return series.rolling(window=window).apply(get_slope, raw=True)


def calculate_cvd_obv_series(
    df: pd.DataFrame,
    slope_window: int = 20,
    norm_window: int = 100,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Calculate CVD (or OBV fallback), delta, cvd_slope, and price_slope series.

    Returns:
        (volume_delta_series, delta_bar, normalized_cvd_slope, normalized_price_slope)
    """
    if len(df) == 0:
        empty = pd.Series(dtype=float)
        return empty, empty, empty, empty

    has_taker = "taker_buy_volume" in df.columns and df["taker_buy_volume"].notna().any()

    if has_taker:
        taker_vol = df["taker_buy_volume"].fillna(0.0)
        tot_vol = df["volume"]
        delta = 2.0 * taker_vol - tot_vol

        # Session reset at 00:00 UTC
        if isinstance(df.index, pd.DatetimeIndex):
            session_dates = df.index.date
        elif "open_time" in df.columns:
            times = pd.to_datetime(df["open_time"], utc=True)
            session_dates = times.dt.date
        else:
            session_dates = np.zeros(len(df))
        cvd = delta.groupby(session_dates).cumsum()
    else:
        # Fallback to OBV
        close = df["close"]
        vol = df["volume"]
        prev_close = close.shift(1).fillna(close)
        direction = np.sign(close - prev_close)
        delta = direction * vol
        cvd = delta.cumsum()

    # Raw slope over slope_window using continuous cumulative delta
    continuous_cum = delta.cumsum()
    raw_cvd_slope = calculate_linear_regression_slope(continuous_cum, window=slope_window)
    raw_price_slope = calculate_linear_regression_slope(df["close"], window=slope_window)

    # Standard deviation over norm_window for normalization
    cvd_std = (
        continuous_cum.rolling(window=norm_window, min_periods=slope_window)
        .std(ddof=0)
        .fillna(1.0)
    )
    price_std = (
        df["close"].rolling(window=norm_window, min_periods=slope_window).std(ddof=0).fillna(1.0)
    )

    # Avoid zero division
    safe_cvd_std = cvd_std.replace(0, np.nan).fillna(1.0)
    safe_price_std = price_std.replace(0, np.nan).fillna(1.0)

    # Scale slope by window to represent normalized delta move
    norm_cvd_slope = (raw_cvd_slope * slope_window / safe_cvd_std).fillna(0.0)
    norm_price_slope = (raw_price_slope * slope_window / safe_price_std).fillna(0.0)

    return cvd, delta, norm_cvd_slope, norm_price_slope


class CvdObvIndicator:
    """Evaluates Cumulative Volume Delta / OBV slope alignment and volume divergence."""

    def __init__(
        self,
        slope_window: int = 20,
        norm_window: int = 100,
        threshold: float = 0.5,
    ) -> None:
        self.slope_window = slope_window
        self.norm_window = norm_window
        self.threshold = threshold

    def evaluate(
        self,
        df: pd.DataFrame,
        context: MarketContext | None = None,
    ) -> IndicatorResult:
        if len(df) < self.slope_window:
            return IndicatorResult(
                key="cvd_obv",
                category="order_flow",
                state="NEUTRAL",
                strength=0.0,
                values={},
                reason="Data candle tidak cukup untuk menghitung CVD/OBV.",
            )

        cvd_s, delta_s, cvd_slope_s, price_slope_s = calculate_cvd_obv_series(
            df,
            slope_window=self.slope_window,
            norm_window=self.norm_window,
        )

        last_cvd = float(cvd_s.iloc[-1])
        last_delta = float(delta_s.iloc[-1])
        cvd_slope = float(cvd_slope_s.iloc[-1])
        price_slope = float(price_slope_s.iloc[-1])

        values = {
            "cvd": round(last_cvd, 2),
            "delta": round(last_delta, 2),
            "cvd_slope": round(cvd_slope, 4),
            "price_slope": round(price_slope, 4),
        }

        # Check divergence:
        # 1. Price rising but CVD falling significantly
        if price_slope > self.threshold and cvd_slope < -self.threshold:
            return IndicatorResult(
                key="cvd_obv",
                category="order_flow",
                state="BEAR",
                strength=0.6,
                values=values,
                reason="Divergensi order flow: kenaikan harga tidak didukung pembeli agresif.",
            )
        # 2. Price falling but CVD rising significantly (absorption)
        if price_slope < -self.threshold and cvd_slope > self.threshold:
            return IndicatorResult(
                key="cvd_obv",
                category="order_flow",
                state="BULL",
                strength=0.6,
                values=values,
                reason="Divergensi order flow: penurunan harga ditahan pembeli agresif (absorpsi).",
            )

        # Standard alignment
        if cvd_slope > self.threshold and price_slope >= 0.0:
            state = "BULL"
            strength = float(np.clip(abs(cvd_slope) / 2.0, 0.0, 1.0))
            reason = f"Pembeli agresif mendominasi order flow (slope CVD {cvd_slope:+.2f})."
        elif cvd_slope < -self.threshold and price_slope <= 0.0:
            state = "BEAR"
            strength = float(np.clip(abs(cvd_slope) / 2.0, 0.0, 1.0))
            reason = f"Penjual agresif mendominasi order flow (slope CVD {cvd_slope:+.2f})."
        else:
            state = "NEUTRAL"
            strength = 0.0
            reason = f"Aktivitas taker volume berimbang atau netral (slope CVD {cvd_slope:+.2f})."

        return IndicatorResult(
            key="cvd_obv",
            category="order_flow",
            state=state,
            strength=round(strength, 4),
            values=values,
            reason=reason,
        )
