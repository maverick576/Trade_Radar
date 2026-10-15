"""Funding rate and Open Interest derivatives indicator with 4-hour change matrix."""

import numpy as np
import pandas as pd

from traderadar.engine.indicators.base import IndicatorResult, MarketContext


class FundingOiIndicator:
    """Evaluates derivatives positioning via 4-hour price and open interest change matrix."""

    def __init__(
        self,
        oi_window_hours: int = 4,
        oi_change_pct: float = 1.0,
        funding_crowded: float = 0.0005,
        funding_negative: float = -0.0003,
    ) -> None:
        self.oi_window_hours = oi_window_hours
        self.oi_change_pct = oi_change_pct
        self.funding_crowded = funding_crowded
        self.funding_negative = funding_negative

    def evaluate(
        self,
        df: pd.DataFrame,
        context: MarketContext | None = None,
    ) -> IndicatorResult:
        # Check context for derivatives metrics
        if (
            context is None
            or context.open_interest_current is None
            or context.open_interest_4h_ago is None
            or context.open_interest_4h_ago <= 0
        ):
            return IndicatorResult(
                key="funding_oi",
                category="derivatives",
                state="NA",
                strength=0.0,
                values={},
                reason="Data Open Interest derivatif tidak tersedia.",
            )

        oi_cur = context.open_interest_current
        oi_prev = context.open_interest_4h_ago
        funding = context.funding_rate or 0.0

        # Calculate delta OI%
        delta_oi_pct = ((oi_cur - oi_prev) / oi_prev) * 100.0

        # Calculate delta Price% over 4 hours (16 bars on M15, or from timestamp)
        if len(df) >= 16:
            price_prev = float(df["close"].iloc[-16])
            price_cur = float(df["close"].iloc[-1])
            delta_price_pct = ((price_cur - price_prev) / price_prev) * 100.0
        elif len(df) >= 2:
            price_prev = float(df["close"].iloc[0])
            price_cur = float(df["close"].iloc[-1])
            delta_price_pct = ((price_cur - price_prev) / price_prev) * 100.0
        else:
            delta_price_pct = 0.0

        values = {
            "funding_rate": round(funding, 6),
            "oi_change_pct": round(delta_oi_pct, 4),
            "price_change_pct": round(delta_price_pct, 4),
            "open_interest": round(oi_cur, 2),
        }

        base_strength = float(np.clip(abs(delta_oi_pct) / 5.0, 0.0, 1.0))

        # Matrix:
        # ΔP > 0 and ΔOI > 1%: BULL (Long baru masuk)
        # ΔP > 0 and ΔOI < -1%: NEUTRAL (Short covering, rapuh)
        # ΔP < 0 and ΔOI > 1%: BEAR (Short baru masuk)
        # ΔP < 0 and ΔOI < -1%: NEUTRAL (Long likuidasi/keluar)
        if delta_price_pct > 0 and delta_oi_pct > self.oi_change_pct:
            state = "BULL"
            reason = (
                f"Akumulasi long baru masuk (ΔOI {delta_oi_pct:+.1f}%, ΔP {delta_price_pct:+.1f}%)."
            )
            strength = base_strength
        elif delta_price_pct > 0 and delta_oi_pct < -self.oi_change_pct:
            state = "NEUTRAL"
            reason = (
                f"Short covering rapuh (ΔOI {delta_oi_pct:+.1f}%, harga naik tanpa open interest)."
            )
            strength = 0.0
        elif delta_price_pct < 0 and delta_oi_pct > self.oi_change_pct:
            state = "BEAR"
            reason = (
                f"Akumulasi short masuk (ΔOI {delta_oi_pct:+.1f}%, ΔP {delta_price_pct:+.1f}%)."
            )
            strength = base_strength
        elif delta_price_pct < 0 and delta_oi_pct < -self.oi_change_pct:
            state = "NEUTRAL"
            reason = f"Likuidasi long (ΔOI {delta_oi_pct:+.1f}%, posisi berkurang saat turun)."
            strength = 0.0
        else:
            state = "NEUTRAL"
            reason = f"Perubahan Open Interest datar (ΔOI {delta_oi_pct:+.1f}%)."
            strength = 0.0

        # Funding overrides:
        # Overly crowded long: funding > 0.05% per 8h
        if funding > self.funding_crowded:
            if state == "BULL":
                state = "NEUTRAL"
                reason = f"Funding tinggi ({funding * 100:+.3f}%), posisi long ramai rawan squeeze."
                strength = 0.0
        # Negative funding while price rising -> short squeeze potential
        elif funding < self.funding_negative and delta_price_pct > 0:
            if state == "BULL":
                strength = min(strength + 0.2, 1.0)
                reason += (
                    f" Funding negatif ({funding * 100:+.3f}%) meningkatkan potensi short squeeze."
                )
            elif state == "NEUTRAL":
                state = "BULL"
                strength = 0.5
                reason = (
                    f"Funding negatif ({funding * 100:+.3f}%) harga naik memicu potensi squeeze."
                )

        return IndicatorResult(
            key="funding_oi",
            category="derivatives",
            state=state,
            strength=round(strength, 4),
            values=values,
            reason=reason,
        )
