"""Strategy A: 10-Indicator Confluence Coordinator."""

from datetime import datetime
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from traderadar.core.config import AppSettings, get_settings
from traderadar.core.time import utc_now
from traderadar.engine.calculator import IndicatorEngine
from traderadar.engine.indicators.base import IndicatorResult, MarketContext
from traderadar.engine.indicators.supertrend import calculate_supertrend_series
from traderadar.engine.macro_filter import (
    MacroFilterContext,
    MacroFilterResult,
    evaluate_macro_filters,
)
from traderadar.engine.scoring import (
    DEFAULT_WEIGHTS,
    H1BiasType,
    VerdictType,
    calculate_confluence_score,
    evaluate_h1_confirmation,
)
from traderadar.engine.strategies.triple_ema import StrategyBResult, evaluate_triple_ema


class SignalRecordPayload(BaseModel):
    """Signal metadata for database persistence and event emission."""

    strategy: str  # "konfluensi10" | "triple_ema"
    symbol: str
    tf: str
    side: Literal["LONG", "SHORT"]
    verdict: str
    bar_time: datetime
    status: Literal["ticketed", "blocked", "watch", "expired"]
    blocked_by: list[str] = Field(default_factory=list)
    confirmed_by_b: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class Analysis(BaseModel):
    """Unified schema representing confluence engine output at a bar close."""

    symbol: str
    tf: str
    bar_time: datetime
    source: str
    indicators: list[IndicatorResult]
    score: float
    counts: dict[str, int]
    category_votes: dict[str, str]
    htf: dict[str, str]  # {"H1": "BULL", "H4": "BULL", "D1": "NEUTRAL"}
    macro: MacroFilterResult
    verdict: VerdictType
    strategy_b: StrategyBResult
    weights_version: str
    created_at: datetime = Field(default_factory=utc_now)


class ConfluencePipeline:
    """End-to-end execution of Strategi A & B."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings().app
        self.calculator = IndicatorEngine(settings=self.settings)

    def evaluate_htf_biases(
        self,
        df_h1: pd.DataFrame | None,
        df_h4: pd.DataFrame | None,
        df_d1: pd.DataFrame | None,
    ) -> tuple[dict[str, str], H1BiasType, float | None, float | None, float | None]:
        """Compute HTF trends (H1 confirmation, H4 EMA200, D1 Supertrend).

        Returns:
            (htf_dict, h1_confirmation, h4_close, h4_ema200, d1_supertrend_dir)
        """
        htf_dict: dict[str, str] = {"H1": "NEUTRAL", "H4": "NEUTRAL", "D1": "NEUTRAL"}
        h1_confirmation: H1BiasType = "NEUTRAL"
        h4_close = None
        h4_ema200 = None
        d1_st_dir = None

        # 1. H1 confirmation
        if df_h1 is not None and len(df_h1) >= 20:
            c = df_h1["close"].astype(float)
            # EMA ribbon state approximation on H1
            ema8 = c.ewm(span=8, adjust=False).mean().iloc[-1]
            ema13 = c.ewm(span=13, adjust=False).mean().iloc[-1]
            ema21 = c.ewm(span=21, adjust=False).mean().iloc[-1]
            ema34 = c.ewm(span=34, adjust=False).mean().iloc[-1]
            ema55 = c.ewm(span=55, adjust=False).mean().iloc[-1]
            h1_ribbon_state = (
                "BULL"
                if (ema8 > ema13 > ema21 > ema34 > ema55 and c.iloc[-1] > ema8)
                else (
                    "BEAR"
                    if (ema8 < ema13 < ema21 < ema34 < ema55 and c.iloc[-1] < ema8)
                    else "NEUTRAL"
                )
            )

            # Supertrend on H1
            _, st_dir, _, _ = calculate_supertrend_series(df_h1, atr_period=10, multiplier=3.0)
            h1_st_state = "BULL" if (not st_dir.empty and st_dir.iloc[-1] > 0) else "BEAR"

            # RSI on H1
            delta = c.diff()
            gain = delta.clip(lower=0.0)
            loss = (-delta).clip(lower=0.0)
            avg_gain = gain.ewm(alpha=1.0 / 14.0, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1.0 / 14.0, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, 1e-9)
            rsi_h1 = float(100.0 - (100.0 / (1.0 + rs)).iloc[-1])

            h1_confirmation = evaluate_h1_confirmation(
                ema_ribbon_state=h1_ribbon_state,
                supertrend_state=h1_st_state,
                rsi_value=rsi_h1,
            )
            htf_dict["H1"] = h1_confirmation

        # 2. H4 close vs EMA200
        if df_h4 is not None and len(df_h4) >= 20:
            c_h4 = df_h4["close"].astype(float)
            h4_close = float(c_h4.iloc[-1])
            # If less than 200 bars, ewm still works smoothly
            ema_period = min(200, len(c_h4))
            h4_ema200 = float(c_h4.ewm(span=ema_period, adjust=False).mean().iloc[-1])
            if h4_close > h4_ema200:
                htf_dict["H4"] = "BULL"
            elif h4_close < h4_ema200:
                htf_dict["H4"] = "BEAR"
            else:
                htf_dict["H4"] = "NEUTRAL"

        # 3. D1 Supertrend
        if df_d1 is not None and len(df_d1) >= 15:
            _, st_d1_dir, _, _ = calculate_supertrend_series(df_d1, atr_period=10, multiplier=3.0)
            if not st_d1_dir.empty:
                d1_st_dir = float(st_d1_dir.iloc[-1])
                htf_dict["D1"] = "BULL" if d1_st_dir > 0 else "BEAR"

        return htf_dict, h1_confirmation, h4_close, h4_ema200, d1_st_dir

    def run_analysis(
        self,
        symbol: str,
        tf: str,
        source: str,
        df_m15: pd.DataFrame,
        df_h1: pd.DataFrame | None = None,
        df_h4: pd.DataFrame | None = None,
        df_d1: pd.DataFrame | None = None,
        context: MarketContext | None = None,
        macro_override: MacroFilterContext | None = None,
        previous_signal_side: str | None = None,
        previous_signal_bars_ago: int | None = None,
    ) -> tuple[Analysis, list[SignalRecordPayload]]:
        """Run full confluence analysis, macro filtering, and signal generation.

        Returns:
            (Analysis, list of SignalRecordPayload)
        """
        if len(df_m15) == 0:
            raise ValueError("DataFrame M15 cannot be empty for analysis.")

        # Determine bar_time
        if "open_time" in df_m15.columns:
            last_open = df_m15["open_time"].iloc[-1]
            bar_time = pd.to_datetime(last_open, utc=True).to_pydatetime()
        elif isinstance(df_m15.index, pd.DatetimeIndex):
            bar_time = df_m15.index[-1].to_pydatetime()
        else:
            bar_time = utc_now()

        is_gold = "XAU" in symbol.upper() or "GOLD" in symbol.upper()

        # 1. Evaluate 10 indicators on M15
        indicators, _ = self.calculator.evaluate_all(df_m15, context=context)

        # 2. HTF analysis
        htf_dict, h1_confirm, h4_close, h4_ema200, d1_st_dir = self.evaluate_htf_biases(
            df_h1, df_h4, df_d1
        )

        # 3. Volatility ATR for M3
        # True range over 14 bars
        high_s = df_m15["high"].astype(float)
        low_s = df_m15["low"].astype(float)
        close_s = df_m15["close"].astype(float)
        tr = pd.concat(
            [high_s - low_s, (high_s - close_s.shift(1)).abs(), (low_s - close_s.shift(1)).abs()],
            axis=1,
        ).max(axis=1)
        atr_series = tr.ewm(alpha=1.0 / 14.0, adjust=False).mean()
        cur_atr = float(atr_series.iloc[-1]) if not atr_series.empty else None

        # Percentile range
        atr_p10 = None
        atr_p95 = None
        if len(atr_series) >= 30:
            atr_p10 = float(
                np.percentile(
                    atr_series.dropna(), self.settings.macro_filter.atr_percentile_range[0]
                )
            )
            atr_p95 = float(
                np.percentile(
                    atr_series.dropna(), self.settings.macro_filter.atr_percentile_range[1]
                )
            )

        # Preliminary score without macro to determine tentative side for M1
        active_weights = self.settings.weights or DEFAULT_WEIGHTS
        prelim_score = calculate_confluence_score(
            indicators=indicators,
            weights=active_weights,
            h1_confirmation=h1_confirm,
            macro_passed=True,
            strong_score=self.settings.verdict.strong_score,
            watch_score=self.settings.verdict.watch_score,
            min_categories=self.settings.verdict.min_categories,
            min_available_weight_pct=self.settings.verdict.min_available_weight_pct,
        )

        tentative_side: Literal["LONG", "SHORT", "NEUTRAL"] = (
            "LONG"
            if prelim_score.score >= self.settings.verdict.watch_score
            else (
                "SHORT" if prelim_score.score <= -self.settings.verdict.watch_score else "NEUTRAL"
            )
        )

        # 4. Evaluate Macro Filter M1-M8
        if macro_override:
            macro_ctx = macro_override
            macro_ctx.side = tentative_side
            macro_ctx.bar_time = bar_time
        else:
            macro_ctx = MacroFilterContext(
                symbol=symbol,
                side=tentative_side,
                bar_time=bar_time,
                h4_close=h4_close,
                h4_ema200=h4_ema200,
                d1_supertrend_dir=d1_st_dir,
                current_atr=cur_atr,
                atr_p10=atr_p10,
                atr_p95=atr_p95,
                is_gold=is_gold,
                funding_rate=context.funding_rate if context else None,
                is_fallback_gold=source.startswith("binance_spot") if is_gold else False,
            )

        macro_res = evaluate_macro_filters(macro_ctx, settings=self.settings.macro_filter)

        # 5. Final Confluence Score & Verdict
        final_score = calculate_confluence_score(
            indicators=indicators,
            weights=active_weights,
            h1_confirmation=h1_confirm,
            macro_passed=macro_res.passed,
            strong_score=self.settings.verdict.strong_score,
            watch_score=self.settings.verdict.watch_score,
            min_categories=self.settings.verdict.min_categories,
            min_available_weight_pct=self.settings.verdict.min_available_weight_pct,
        )

        final_verdict = final_score.verdict

        # Cooldown check:
        # After a STRONG signal on symbol, subsequent signal in same direction
        # is ignored for cooldown_bars
        if (
            final_verdict in ("STRONG_LONG", "STRONG_SHORT")
            and previous_signal_side is not None
            and previous_signal_bars_ago is not None
            and previous_signal_bars_ago <= self.settings.verdict.cooldown_bars
        ):
            target_side = "LONG" if final_verdict == "STRONG_LONG" else "SHORT"
            if previous_signal_side == target_side:
                # Downgrade to watch signal on cooldown
                final_verdict = "LONG" if final_verdict == "STRONG_LONG" else "SHORT"

        # 6. Evaluate Strategy B (Triple-EMA)
        strategy_b_res = evaluate_triple_ema(
            df_m15=df_m15,
            df_h1=df_h1,
            macro_result=macro_res,
            settings=self.settings.strategy_b_triple_ema,
        )

        # Assemble Analysis
        analysis = Analysis(
            symbol=symbol,
            tf=tf,
            bar_time=bar_time,
            source=source,
            indicators=indicators,
            score=final_score.score,
            counts=final_score.counts,
            category_votes=final_score.category_votes,
            htf=htf_dict,
            macro=macro_res,
            verdict=final_verdict,
            strategy_b=strategy_b_res,
            weights_version=self.settings.weights_version,
            created_at=utc_now(),
        )

        # Generate Signals (both Strategi A & Strategi B)
        signals: list[SignalRecordPayload] = []

        # Strategi A Signal
        if final_verdict != "NEUTRAL":
            side: Literal["LONG", "SHORT"] = "LONG" if "LONG" in final_verdict else "SHORT"
            is_strong = "STRONG" in final_verdict

            status: Literal["ticketed", "blocked", "watch", "expired"] = "watch"
            if is_strong:
                status = "ticketed" if macro_res.passed else "blocked"
            elif not macro_res.passed:
                status = "blocked"

            confirmed_by_b = strategy_b_res.state == side and strategy_b_res.confirmed

            signals.append(
                SignalRecordPayload(
                    strategy="konfluensi10",
                    symbol=symbol,
                    tf=tf,
                    side=side,
                    verdict=final_verdict,
                    bar_time=bar_time,
                    status=status,
                    blocked_by=macro_res.blocked_by,
                    confirmed_by_b=confirmed_by_b,
                    created_at=utc_now(),
                )
            )

        # Strategi B Signal
        if strategy_b_res.state in ("LONG", "SHORT"):
            b_side = strategy_b_res.state
            b_status: Literal["ticketed", "blocked", "watch", "expired"] = (
                "ticketed" if strategy_b_res.confirmed else "blocked"
            )
            signals.append(
                SignalRecordPayload(
                    strategy="triple_ema",
                    symbol=symbol,
                    tf=tf,
                    side=b_side,
                    verdict=f"STRATEGY_B_{b_side}",
                    bar_time=bar_time,
                    status=b_status,
                    blocked_by=[
                        chk.id
                        for chk in macro_res.checks
                        if chk.id in ("M2", "M3", "M4", "M5", "M6") and not chk.passed
                    ],
                    confirmed_by_b=True,
                    created_at=utc_now(),
                )
            )

        return analysis, signals
