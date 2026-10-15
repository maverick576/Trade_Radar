"""LightGBM machine learning indicator with triple-barrier probabilities and OOS AUC validation."""

import numpy as np
import pandas as pd

from traderadar.engine.indicators.base import IndicatorResult, MarketContext


class LightGbmIndicator:
    """Evaluates machine learning model probability output against threshold margins."""

    def __init__(
        self,
        horizon_bars: int = 16,
        barrier_atr: float = 1.5,
        p_threshold: float = 0.58,
        p_margin: float = 0.15,
        min_auc: float = 0.55,
    ) -> None:
        self.horizon_bars = horizon_bars
        self.barrier_atr = barrier_atr
        self.p_threshold = p_threshold
        self.p_margin = p_margin
        self.min_auc = min_auc

    def evaluate(
        self,
        df: pd.DataFrame,
        context: MarketContext | None = None,
    ) -> IndicatorResult:
        if context is None or context.model_predictions is None:
            return IndicatorResult(
                key="lightgbm",
                category="ml",
                state="NA",
                strength=0.0,
                values={},
                reason="Model belum cukup akurat atau belum dilatih.",
            )

        auc = context.model_auc or 0.50
        if auc < self.min_auc:
            return IndicatorResult(
                key="lightgbm",
                category="ml",
                state="NA",
                strength=0.0,
                values={"auc": round(auc, 4)},
                reason=f"Model belum aktif (AUC {auc:.2f} < ambang minimum {self.min_auc:.2f}).",
            )

        p_up, p_down = context.model_predictions
        values = {
            "p_up": round(p_up, 4),
            "p_down": round(p_down, 4),
            "auc": round(auc, 4),
        }

        # BULL: p_up >= 0.58 and p_up - p_down >= 0.15
        if p_up >= self.p_threshold and (p_up - p_down) >= self.p_margin:
            state = "BULL"
            strength = float(np.clip((p_up - 0.5) / 0.25, 0.0, 1.0))
            reason = (
                f"Prediksi model cenderung naik (P(up)={p_up:.1%}, delta={p_up - p_down:+.1%})."
            )
        # BEAR: p_down >= 0.58 and p_down - p_up >= 0.15
        elif p_down >= self.p_threshold and (p_down - p_up) >= self.p_margin:
            state = "BEAR"
            strength = float(np.clip((p_down - 0.5) / 0.25, 0.0, 1.0))
            reason = (
                f"Prediksi model turun (P(down)={p_down:.1%}, delta={p_down - p_up:+.1%})."
            )
        else:
            state = "NEUTRAL"
            strength = 0.0
            reason = f"Probabilitas arah pasar berimbang (P(up)={p_up:.1%}, P(down)={p_down:.1%})."

        return IndicatorResult(
            key="lightgbm",
            category="ml",
            state=state,
            strength=round(strength, 4),
            values=values,
            reason=reason,
        )
