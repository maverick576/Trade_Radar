"""Session Volume Weighted Average Price (VWAP) with standard deviation bands."""

import numpy as np
import pandas as pd

from traderadar.engine.indicators.base import IndicatorResult, MarketContext


def calculate_vwap_series(
    df: pd.DataFrame,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    """Calculate session VWAP reset at 00:00 UTC and deviation bands.

    Returns:
        (vwap, upper_1, lower_1, upper_2, lower_2, sigma, z_score, slope)
    """
    if len(df) == 0:
        empty = pd.Series(dtype=float)
        return empty, empty, empty, empty, empty, empty, empty, empty

    # Typical price
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"]
    pv = tp * vol
    pv2 = (tp**2) * vol

    # Identify 00:00 UTC session dates
    if isinstance(df.index, pd.DatetimeIndex):
        session_dates = df.index.date
    elif "open_time" in df.columns:
        times = pd.to_datetime(df["open_time"], utc=True)
        session_dates = times.dt.date
    else:
        # Fallback to single session
        session_dates = np.zeros(len(df))

    # Groupby session date and calculate cumulative sums
    cum_vol = vol.groupby(session_dates).cumsum()
    cum_pv = pv.groupby(session_dates).cumsum()
    cum_pv2 = pv2.groupby(session_dates).cumsum()

    # Avoid division by zero
    safe_cum_vol = cum_vol.replace(0, np.nan)
    vwap = cum_pv / safe_cum_vol
    vwap = vwap.ffill().fillna(tp)

    # Volume-weighted variance: E[X^2] - (E[X])^2
    var = (cum_pv2 / safe_cum_vol) - (vwap**2)
    # Clip small negative values due to floating-point imprecision
    var = var.clip(lower=0.0)
    sigma = np.sqrt(var).fillna(0.0)

    upper_1 = vwap + sigma
    lower_1 = vwap - sigma
    upper_2 = vwap + 2.0 * sigma
    lower_2 = vwap - 2.0 * sigma

    safe_sigma = sigma.replace(0, np.nan)
    z_score = ((df["close"] - vwap) / safe_sigma).fillna(0.0)

    # slope = vwap_t - vwap_{t-4} within the same session
    shifted_vwap = vwap.groupby(session_dates).shift(4)
    slope = (vwap - shifted_vwap).fillna(0.0)

    return vwap, upper_1, lower_1, upper_2, lower_2, sigma, z_score, slope


class VwapIndicator:
    """Evaluates VWAP and standard deviation bands on closed candle DataFrame."""

    def __init__(
        self,
        z_threshold: float = 0.25,
        overextended_z: float = 2.0,
    ) -> None:
        self.z_threshold = z_threshold
        self.overextended_z = overextended_z

    def evaluate(
        self,
        df: pd.DataFrame,
        context: MarketContext | None = None,
    ) -> IndicatorResult:
        if len(df) < 5:
            return IndicatorResult(
                key="vwap",
                category="order_flow",
                state="NEUTRAL",
                strength=0.0,
                values={},
                reason="Data candle tidak cukup untuk menghitung VWAP.",
            )

        vwap, up1, dn1, up2, dn2, sigma, z, slope = calculate_vwap_series(df)

        last_vwap = float(vwap.iloc[-1])
        last_sigma = float(sigma.iloc[-1])
        last_up1 = float(up1.iloc[-1])
        last_dn1 = float(dn1.iloc[-1])
        last_up2 = float(up2.iloc[-1])
        last_dn2 = float(dn2.iloc[-1])
        last_z = float(z.iloc[-1])
        last_slope = float(slope.iloc[-1])

        # Bars count in current session
        if isinstance(df.index, pd.DatetimeIndex):
            cur_date = df.index[-1].date()
            session_bars = int((df.index.date == cur_date).sum())
        elif "open_time" in df.columns:
            times = pd.to_datetime(df["open_time"], utc=True)
            cur_date = times.iloc[-1].date()
            session_bars = int((times.dt.date == cur_date).sum())
        else:
            session_bars = len(df)

        values = {
            "vwap": round(last_vwap, 4),
            "sigma": round(last_sigma, 4),
            "upper_1": round(last_up1, 4),
            "lower_1": round(last_dn1, 4),
            "upper_2": round(last_up2, 4),
            "lower_2": round(last_dn2, 4),
            "z": round(last_z, 4),
            "slope": round(last_slope, 4),
        }

        # First 4 bars after reset -> NEUTRAL
        if session_bars <= 4:
            return IndicatorResult(
                key="vwap",
                category="order_flow",
                state="NEUTRAL",
                strength=0.0,
                values=values,
                reason="VWAP belum stabil pada awal sesi (kurang dari 4 bar).",
            )

        # Bull / Bear conditions
        if last_z > self.z_threshold and last_slope > 0:
            state = "BULL"
        elif last_z < -self.z_threshold and last_slope < 0:
            state = "BEAR"
        else:
            state = "NEUTRAL"

        # Strength calculation: min(|z|/2, 1)
        base_strength = min(abs(last_z) / 2.0, 1.0)
        is_overextended = abs(last_z) > self.overextended_z

        if is_overextended:
            strength = base_strength * 0.5
            if state == "BULL":
                reason = f"Harga terlalu jauh di atas VWAP (z={last_z:+.2f}), rawan mean-reversion."
            elif state == "BEAR":
                reason = (
                    f"Harga terlalu jauh di bawah VWAP (z={last_z:+.2f}), rawan mean-reversion."
                )
            else:
                reason = f"Harga terlalu jauh dari VWAP (z={last_z:+.2f}), rawan mean-reversion."
        else:
            strength = base_strength
            if state == "BULL":
                reason = f"Harga di atas VWAP (z={last_z:+.2f}) dengan kemiringan naik."
            elif state == "BEAR":
                reason = f"Harga di bawah VWAP (z={last_z:+.2f}) dengan kemiringan turun."
            else:
                reason = f"Harga berada di sekitar VWAP (z={last_z:+.2f}) atau kemiringan mendatar."

        return IndicatorResult(
            key="vwap",
            category="order_flow",
            state=state,
            strength=round(strength, 4),
            values=values,
            reason=reason,
        )
