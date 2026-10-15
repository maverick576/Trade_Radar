"""Market sentiment indicator combining Fear & Greed index and Long/Short ratio contrarian rules."""

import pandas as pd

from traderadar.engine.indicators.base import IndicatorResult, MarketContext


class SentimentIndicator:
    """Evaluates contrarian sentiment signals from Fear & Greed and Binance Long/Short ratio."""

    def __init__(
        self,
        fng_fear: int = 20,
        fng_greed: int = 80,
        ls_high: float = 2.5,
        ls_low: float = 0.7,
    ) -> None:
        self.fng_fear = fng_fear
        self.fng_greed = fng_greed
        self.ls_high = ls_high
        self.ls_low = ls_low

    def evaluate(
        self,
        df: pd.DataFrame,
        context: MarketContext | None = None,
    ) -> IndicatorResult:
        if context is None:
            return IndicatorResult(
                key="sentiment",
                category="sentiment",
                state="NA",
                strength=0.0,
                values={},
                reason="Data sentimen pasar tidak tersedia.",
            )

        is_gold = context.is_gold
        ls_ratio = context.long_short_ratio
        fng = context.fear_and_greed

        # For Gold: only LS ratio is used
        if is_gold:
            if ls_ratio is None or ls_ratio <= 0:
                return IndicatorResult(
                    key="sentiment",
                    category="sentiment",
                    state="NA",
                    strength=0.0,
                    values={},
                    reason="Rasio Long/Short akun Gold tidak tersedia.",
                )

            values = {"long_short_ratio": round(ls_ratio, 4)}
            if ls_ratio > self.ls_high:
                return IndicatorResult(
                    key="sentiment",
                    category="sentiment",
                    state="BEAR",
                    strength=0.4,
                    values=values,
                    reason=(
                        f"Rasio Long/Short ({ls_ratio:.2f} > {self.ls_high:.1f}) contrarian sell."
                    ),
                )
            if ls_ratio < self.ls_low:
                return IndicatorResult(
                    key="sentiment",
                    category="sentiment",
                    state="BULL",
                    strength=0.4,
                    values=values,
                    reason=(
                        f"Rasio Long/Short ({ls_ratio:.2f} < {self.ls_low:.1f}) contrarian buy."
                    ),
                )

            return IndicatorResult(
                key="sentiment",
                category="sentiment",
                state="NEUTRAL",
                strength=0.0,
                values=values,
                reason=f"Rasio Long/Short seimbang ({ls_ratio:.2f}).",
            )

        # For Crypto: combines Fear & Greed and Long/Short ratio
        if fng is None and ls_ratio is None:
            return IndicatorResult(
                key="sentiment",
                category="sentiment",
                state="NA",
                strength=0.0,
                values={},
                reason="Data sentimen Fear & Greed dan rasio L/S crypto tidak tersedia.",
            )

        # Signed score components (+ for bull, - for bear)
        signed_scores: list[float] = []
        notes: list[str] = []

        if fng is not None:
            if fng <= self.fng_fear:
                signed_scores.append(0.5)
                notes.append(f"Extreme Fear ({fng})")
            elif fng >= self.fng_greed:
                signed_scores.append(-0.5)
                notes.append(f"Extreme Greed ({fng})")
            else:
                signed_scores.append(0.0)
                notes.append(f"F&G Netral ({fng})")

        if ls_ratio is not None and ls_ratio > 0:
            if ls_ratio > self.ls_high:
                signed_scores.append(-0.4)
                notes.append(f"Long crowded ({ls_ratio:.2f})")
            elif ls_ratio < self.ls_low:
                signed_scores.append(0.4)
                notes.append(f"Short crowded ({ls_ratio:.2f})")
            else:
                signed_scores.append(0.0)
                notes.append(f"L/S seimbang ({ls_ratio:.2f})")

        combined_score = sum(signed_scores) / len(signed_scores) if signed_scores else 0.0

        values = {
            "fear_and_greed": float(fng) if fng is not None else -1.0,
            "long_short_ratio": round(ls_ratio, 4) if ls_ratio is not None else -1.0,
            "sentiment_score": round(combined_score, 4),
        }

        if combined_score >= 0.2:
            state = "BULL"
            strength = min(abs(combined_score), 1.0)
            reason = f"Sentimen kontrarian bullish: {', '.join(notes)}."
        elif combined_score <= -0.2:
            state = "BEAR"
            strength = min(abs(combined_score), 1.0)
            reason = f"Sentimen kontrarian bearish: {', '.join(notes)}."
        else:
            state = "NEUTRAL"
            strength = 0.0
            reason = f"Sentimen agregat netral: {', '.join(notes)}."

        return IndicatorResult(
            key="sentiment",
            category="sentiment",
            state=state,
            strength=round(strength, 4),
            values=values,
            reason=reason,
        )
