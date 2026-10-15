"""Engine indicator evaluator and chart overlay generator with benchmark profiling."""

import time
from typing import Any

import pandas as pd

from traderadar.core.config import AppSettings, get_settings
from traderadar.engine.indicators import (
    BollingerBandsIndicator,
    CvdObvIndicator,
    EmaRibbonIndicator,
    FundingOiIndicator,
    IndicatorResult,
    LightGbmIndicator,
    MarketContext,
    OrderbookIndicator,
    RsiDivergenceIndicator,
    SentimentIndicator,
    SupertrendIndicator,
    VwapIndicator,
    calculate_bollinger_series,
    calculate_cvd_obv_series,
    calculate_ema_ribbon_series,
    calculate_rsi_series,
    calculate_supertrend_series,
    calculate_vwap_series,
)


class IndicatorEngine:
    """Evaluates all 10 trading indicators according to SIGNAL_ENGINE.md."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings().app
        cfg = self.settings.indicators

        self.vwap = VwapIndicator(
            z_threshold=cfg.vwap.z_threshold,
            overextended_z=cfg.vwap.overextended_z,
        )
        self.ema_ribbon = EmaRibbonIndicator(periods=cfg.ema_ribbon.periods)
        self.supertrend = SupertrendIndicator(
            atr_period=cfg.supertrend.atr_period,
            multiplier=cfg.supertrend.multiplier,
            recent_flip_bars=cfg.supertrend.recent_flip_bars,
        )
        self.rsi_div = RsiDivergenceIndicator(
            period=cfg.rsi_div.period,
            pivot_left=cfg.rsi_div.pivot_left,
            pivot_right=cfg.rsi_div.pivot_right,
            min_gap=cfg.rsi_div.min_gap,
            max_gap=cfg.rsi_div.max_gap,
            valid_bars=cfg.rsi_div.valid_bars,
        )
        self.bollinger = BollingerBandsIndicator(
            period=cfg.bollinger.period,
            std=cfg.bollinger.std,
            squeeze_pct=cfg.bollinger.squeeze_pct,
            squeeze_lookback=cfg.bollinger.squeeze_lookback,
        )
        self.cvd_obv = CvdObvIndicator(
            slope_window=cfg.cvd_obv.slope_window,
            norm_window=cfg.cvd_obv.norm_window,
            threshold=cfg.cvd_obv.threshold,
        )
        self.funding_oi = FundingOiIndicator(
            oi_window_hours=cfg.funding_oi.oi_window_hours,
            oi_change_pct=cfg.funding_oi.oi_change_pct,
            funding_crowded=cfg.funding_oi.funding_crowded,
            funding_negative=cfg.funding_oi.funding_negative,
        )
        self.orderbook = OrderbookIndicator(
            depth_pct=cfg.orderbook.depth_pct,
            smooth_seconds=cfg.orderbook.smooth_seconds,
            threshold=cfg.orderbook.threshold,
        )
        self.lightgbm = LightGbmIndicator(
            horizon_bars=cfg.lightgbm.horizon_bars,
            barrier_atr=cfg.lightgbm.barrier_atr,
            p_threshold=cfg.lightgbm.p_threshold,
            p_margin=cfg.lightgbm.p_margin,
            min_auc=cfg.lightgbm.min_auc,
        )
        self.sentiment = SentimentIndicator(
            fng_fear=cfg.sentiment.fng_fear,
            fng_greed=cfg.sentiment.fng_greed,
            ls_high=cfg.sentiment.ls_high,
            ls_low=cfg.sentiment.ls_low,
        )

    def evaluate_all(
        self,
        df: pd.DataFrame,
        context: MarketContext | None = None,
    ) -> tuple[list[IndicatorResult], float]:
        """Compute all 10 indicators on candle DataFrame and context.

        Returns:
            (results, elapsed_milliseconds)
        """
        start = time.perf_counter()

        results = [
            self.vwap.evaluate(df, context),
            self.ema_ribbon.evaluate(df, context),
            self.supertrend.evaluate(df, context),
            self.rsi_div.evaluate(df, context),
            self.bollinger.evaluate(df, context),
            self.cvd_obv.evaluate(df, context),
            self.funding_oi.evaluate(df, context),
            self.orderbook.evaluate(df, context),
            self.lightgbm.evaluate(df, context),
            self.sentiment.evaluate(df, context),
        ]

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return results, elapsed_ms

    def generate_chart_overlays_and_panes(
        self,
        df: pd.DataFrame,
        limit: int = 300,
    ) -> dict[str, Any]:
        """Generate indicator timeseries for TradingView Lightweight Charts overlays and panes."""
        if len(df) == 0:
            return {"overlays": {}, "panes": {}}

        # Slice to recent bars for charting if needed
        work_df = df.iloc[-limit:].copy() if len(df) > limit else df.copy()

        # Extract timestamps in unix epoch seconds
        if "open_time" in work_df.columns:
            times = (pd.to_datetime(work_df["open_time"], utc=True).astype("int64") // 10**9).values
        elif isinstance(work_df.index, pd.DatetimeIndex):
            times = (work_df.index.astype("int64") // 10**9).values
        else:
            times = work_df.index.values

        # 1. VWAP & Bands
        vwap, up1, dn1, up2, dn2, _, _, _ = calculate_vwap_series(work_df)
        vwap_data = [
            {
                "time": int(times[i]),
                "vwap": round(float(vwap.iloc[i]), 4),
                "upper_1": round(float(up1.iloc[i]), 4),
                "lower_1": round(float(dn1.iloc[i]), 4),
                "upper_2": round(float(up2.iloc[i]), 4),
                "lower_2": round(float(dn2.iloc[i]), 4),
            }
            for i in range(len(work_df))
            if pd.notna(vwap.iloc[i])
        ]

        # 2. EMA Ribbon
        emas = calculate_ema_ribbon_series(work_df, [8, 13, 21, 34, 55])
        ema_data = [
            {
                "time": int(times[i]),
                "ema8": round(float(emas[8].iloc[i]), 4),
                "ema13": round(float(emas[13].iloc[i]), 4),
                "ema21": round(float(emas[21].iloc[i]), 4),
                "ema34": round(float(emas[34].iloc[i]), 4),
                "ema55": round(float(emas[55].iloc[i]), 4),
            }
            for i in range(len(work_df))
            if pd.notna(emas[55].iloc[i])
        ]

        # 3. Supertrend
        st, direction, _, _ = calculate_supertrend_series(work_df, atr_period=10, multiplier=3.0)
        supertrend_data = [
            {
                "time": int(times[i]),
                "supertrend": round(float(st.iloc[i]), 4),
                "direction": float(direction.iloc[i]),
            }
            for i in range(len(work_df))
            if pd.notna(st.iloc[i])
        ]

        # 4. Bollinger Bands
        mid, upper, lower, pb, bw, sq = calculate_bollinger_series(work_df, period=20, std_mult=2.0)
        bollinger_data = [
            {
                "time": int(times[i]),
                "mid": round(float(mid.iloc[i]), 4),
                "upper": round(float(upper.iloc[i]), 4),
                "lower": round(float(lower.iloc[i]), 4),
                "percent_b": round(float(pb.iloc[i]), 4),
                "is_squeeze": bool(sq.iloc[i] == 1.0),
            }
            for i in range(len(work_df))
            if pd.notna(mid.iloc[i])
        ]

        # 5. RSI Pane
        rsi_series = calculate_rsi_series(work_df, period=14)
        rsi_data = [
            {
                "time": int(times[i]),
                "value": round(float(rsi_series.iloc[i]), 2),
            }
            for i in range(len(work_df))
            if pd.notna(rsi_series.iloc[i])
        ]

        # 6. CVD Pane
        cvd_series, delta_series, _, _ = calculate_cvd_obv_series(work_df)
        cvd_data = [
            {
                "time": int(times[i]),
                "cvd": round(float(cvd_series.iloc[i]), 2),
                "delta": round(float(delta_series.iloc[i]), 2),
            }
            for i in range(len(work_df))
            if pd.notna(cvd_series.iloc[i])
        ]

        return {
            "overlays": {
                "vwap": vwap_data,
                "ema_ribbon": ema_data,
                "supertrend": supertrend_data,
                "bollinger": bollinger_data,
            },
            "panes": {
                "rsi": rsi_data,
                "cvd": cvd_data,
            },
        }
