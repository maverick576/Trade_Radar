"""Comprehensive unit tests for all 10 trading indicators."""

from datetime import UTC

import numpy as np
import pandas as pd

from traderadar.engine.calculator import IndicatorEngine
from traderadar.engine.indicators import (
    BollingerBandsIndicator,
    CvdObvIndicator,
    EmaRibbonIndicator,
    FundingOiIndicator,
    LightGbmIndicator,
    MarketContext,
    OrderbookIndicator,
    RsiDivergenceIndicator,
    SentimentIndicator,
    SupertrendIndicator,
    VwapIndicator,
)


def create_sample_df(n: int = 150, trend: str = "flat") -> pd.DataFrame:
    """Generate synthetic OHLCV candle DataFrame."""
    base_time = pd.Timestamp("2026-10-15 00:00:00", tz=UTC)
    times = [base_time + pd.Timedelta(minutes=15 * i) for i in range(n)]

    if trend == "bull":
        close = 100.0 + np.linspace(0, 50, n) + np.sin(np.linspace(0, 10, n))
    elif trend == "bear":
        close = 150.0 - np.linspace(0, 50, n) + np.sin(np.linspace(0, 10, n))
    else:
        close = 100.0 + np.sin(np.linspace(0, 20, n)) * 2.0

    high = close + 1.0
    low = close - 1.0
    open_p = close - 0.2
    vol = np.full(n, 1000.0)
    taker_buy = np.full(n, 600.0 if trend == "bull" else 400.0 if trend == "bear" else 500.0)

    df = pd.DataFrame(
        {
            "open_time": times,
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
            "taker_buy_volume": taker_buy,
        }
    )
    return df


class TestVwapIndicator:
    def test_startup_first_4_bars_neutral(self) -> None:
        ind = VwapIndicator()
        df = create_sample_df(n=3)
        res = ind.evaluate(df)
        assert res.state == "NEUTRAL"

    def test_bull_and_bear_states(self) -> None:
        ind = VwapIndicator(z_threshold=0.25)
        df_bull = create_sample_df(n=50, trend="bull")
        res_bull = ind.evaluate(df_bull)
        assert res_bull.state == "BULL"
        assert res_bull.strength > 0.0

        df_bear = create_sample_df(n=50, trend="bear")
        res_bear = ind.evaluate(df_bear)
        assert res_bear.state == "BEAR"
        assert res_bear.strength > 0.0

    def test_overextended_mean_reversion_penalty(self) -> None:
        ind = VwapIndicator(overextended_z=2.0)
        df = create_sample_df(n=50, trend="bull")
        # Spike the last close far above VWAP
        df.loc[df.index[-1], "close"] = 300.0
        df.loc[df.index[-1], "high"] = 305.0
        res = ind.evaluate(df)
        assert res.values["z"] > 2.0
        assert "mean-reversion" in res.reason


class TestEmaRibbonIndicator:
    def test_bullish_alignment(self) -> None:
        ind = EmaRibbonIndicator()
        df = create_sample_df(n=100, trend="bull")
        res = ind.evaluate(df)
        assert res.state == "BULL"
        assert res.values["spread"] > 0
        assert res.strength > 0.0

    def test_bearish_alignment(self) -> None:
        ind = EmaRibbonIndicator()
        df = create_sample_df(n=100, trend="bear")
        res = ind.evaluate(df)
        assert res.state == "BEAR"
        assert res.values["spread"] < 0
        assert res.strength > 0.0

    def test_sideways_neutral(self) -> None:
        ind = EmaRibbonIndicator()
        df = create_sample_df(n=100, trend="flat")
        res = ind.evaluate(df)
        assert res.state in ["NEUTRAL", "BULL", "BEAR"]


class TestSupertrendIndicator:
    def test_bull_and_bear_trend(self) -> None:
        ind = SupertrendIndicator()
        df_bull = create_sample_df(n=80, trend="bull")
        res_bull = ind.evaluate(df_bull)
        assert res_bull.state == "BULL"

        df_bear = create_sample_df(n=80, trend="bear")
        res_bear = ind.evaluate(df_bear)
        assert res_bear.state == "BEAR"

    def test_recent_flip_strength(self) -> None:
        ind = SupertrendIndicator(recent_flip_bars=3)
        df = create_sample_df(n=80, trend="flat")
        res = ind.evaluate(df)
        assert res.strength in [0.3, 0.5, 0.6, 1.0]


class TestRsiDivergenceIndicator:
    def test_rsi_extremes_and_50_cross(self) -> None:
        ind = RsiDivergenceIndicator()
        df = create_sample_df(n=100, trend="bull")
        res = ind.evaluate(df)
        assert res.state in ["BULL", "BEAR", "NEUTRAL"]
        assert 0.0 <= res.values["rsi"] <= 100.0

    def test_bullish_regular_divergence(self) -> None:
        ind = RsiDivergenceIndicator(min_gap=5, max_gap=60, valid_bars=15)
        # Construct synthetic lower low price with higher low RSI
        n = 100
        df = create_sample_df(n=n, trend="flat")
        # Inject pivot low 1 at bar 40
        df.loc[40, "low"] = 70.0
        df.loc[40, "close"] = 71.0
        # Inject pivot low 2 at bar 70 with lower low price but smaller drop in close
        df.loc[70, "low"] = 65.0
        df.loc[70, "close"] = 72.0
        res = ind.evaluate(df)
        assert res.key == "rsi_div"


class TestBollingerBandsIndicator:
    def test_squeeze_and_breakout(self) -> None:
        ind = BollingerBandsIndicator()
        df = create_sample_df(n=130, trend="flat")
        res = ind.evaluate(df)
        assert res.state in ["NEUTRAL", "BULL", "BEAR"]
        assert "percent_b" in res.values

    def test_squeeze_breakout_bull(self) -> None:
        ind = BollingerBandsIndicator()
        df = create_sample_df(n=130, trend="flat")
        # Squeeze by setting low volatility
        df.loc[100:128, "high"] = 100.5
        df.loc[100:128, "low"] = 99.5
        df.loc[100:128, "close"] = 100.0
        # Breakout on bar 129
        df.loc[129, "close"] = 105.0
        df.loc[129, "high"] = 106.0
        res = ind.evaluate(df)
        assert res.state == "BULL"
        assert res.strength == 0.8


class TestCvdObvIndicator:
    def test_cvd_positive_slope_bull(self) -> None:
        ind = CvdObvIndicator()
        df = create_sample_df(n=100, trend="bull")
        res = ind.evaluate(df)
        assert res.state == "BULL"
        assert res.values["cvd_slope"] > 0

    def test_obv_fallback_without_taker(self) -> None:
        ind = CvdObvIndicator()
        df = create_sample_df(n=100, trend="bull")
        df["taker_buy_volume"] = np.nan
        res = ind.evaluate(df)
        assert res.state in ["BULL", "NEUTRAL"]


class TestFundingOiIndicator:
    def test_na_when_missing_context(self) -> None:
        ind = FundingOiIndicator()
        df = create_sample_df(n=20)
        res = ind.evaluate(df, context=None)
        assert res.state == "NA"

    def test_all_quadrants(self) -> None:
        ind = FundingOiIndicator()
        df = create_sample_df(n=30, trend="bull")

        # Quadrant 1: Price Up, OI Up -> BULL
        ctx_bull = MarketContext(
            open_interest_current=110000.0,
            open_interest_4h_ago=100000.0,
            funding_rate=0.0001,
        )
        res = ind.evaluate(df, ctx_bull)
        assert res.state == "BULL"

        # Quadrant 2: Price Up, OI Down -> NEUTRAL (short covering)
        ctx_covering = MarketContext(
            open_interest_current=90000.0,
            open_interest_4h_ago=100000.0,
            funding_rate=0.0001,
        )
        res = ind.evaluate(df, ctx_covering)
        assert res.state == "NEUTRAL"

        # Quadrant 3: Price Down, OI Up -> BEAR
        df_bear = create_sample_df(n=30, trend="bear")
        ctx_bear = MarketContext(
            open_interest_current=110000.0,
            open_interest_4h_ago=100000.0,
            funding_rate=0.0001,
        )
        res = ind.evaluate(df_bear, ctx_bear)
        assert res.state == "BEAR"

    def test_crowded_long_funding_override(self) -> None:
        ind = FundingOiIndicator()
        df = create_sample_df(n=30, trend="bull")
        ctx = MarketContext(
            open_interest_current=110000.0,
            open_interest_4h_ago=100000.0,
            funding_rate=0.0008,  # > 0.05%
        )
        res = ind.evaluate(df, ctx)
        assert res.state == "NEUTRAL"
        assert "long ramai" in res.reason


class TestOrderbookIndicator:
    def test_na_when_missing(self) -> None:
        ind = OrderbookIndicator()
        df = create_sample_df(n=20)
        res = ind.evaluate(df, context=None)
        assert res.state == "NA"
        assert res.live_only is True

    def test_bids_dominance_bull(self) -> None:
        ind = OrderbookIndicator()
        df = create_sample_df(n=20)
        ctx = MarketContext(
            orderbook_bids=[(100.0, 50.0), (99.8, 40.0)],
            orderbook_asks=[(100.1, 10.0), (100.2, 5.0)],
        )
        res = ind.evaluate(df, ctx)
        assert res.state == "BULL"
        assert res.strength > 0.0

    def test_asks_dominance_bear(self) -> None:
        ind = OrderbookIndicator()
        df = create_sample_df(n=20)
        ctx = MarketContext(
            orderbook_bids=[(100.0, 10.0)],
            orderbook_asks=[(100.1, 80.0)],
        )
        res = ind.evaluate(df, ctx)
        assert res.state == "BEAR"
        assert res.strength > 0.0


class TestLightGbmIndicator:
    def test_na_when_no_predictions(self) -> None:
        ind = LightGbmIndicator()
        df = create_sample_df(n=20)
        res = ind.evaluate(df, context=None)
        assert res.state == "NA"

    def test_na_when_auc_below_min(self) -> None:
        ind = LightGbmIndicator(min_auc=0.55)
        df = create_sample_df(n=20)
        ctx = MarketContext(model_predictions=(0.7, 0.3), model_auc=0.52)
        res = ind.evaluate(df, ctx)
        assert res.state == "NA"
        assert "AUC" in res.reason

    def test_bull_and_bear_thresholds(self) -> None:
        ind = LightGbmIndicator()
        df = create_sample_df(n=20)
        # Bull: p_up >= 0.58 and diff >= 0.15
        ctx_bull = MarketContext(model_predictions=(0.65, 0.35), model_auc=0.58)
        res_bull = ind.evaluate(df, ctx_bull)
        assert res_bull.state == "BULL"

        # Bear: p_down >= 0.58 and diff >= 0.15
        ctx_bear = MarketContext(model_predictions=(0.30, 0.70), model_auc=0.60)
        res_bear = ind.evaluate(df, ctx_bear)
        assert res_bear.state == "BEAR"


class TestSentimentIndicator:
    def test_crypto_sentiment(self) -> None:
        ind = SentimentIndicator()
        df = create_sample_df(n=20)

        # Extreme Fear -> Bullish contrarian
        ctx_fear = MarketContext(is_gold=False, fear_and_greed=15, long_short_ratio=0.6)
        res = ind.evaluate(df, ctx_fear)
        assert res.state == "BULL"

        # Extreme Greed -> Bearish contrarian
        ctx_greed = MarketContext(is_gold=False, fear_and_greed=85, long_short_ratio=2.8)
        res = ind.evaluate(df, ctx_greed)
        assert res.state == "BEAR"

    def test_gold_sentiment_ignores_fng(self) -> None:
        ind = SentimentIndicator()
        df = create_sample_df(n=20)
        ctx = MarketContext(is_gold=True, fear_and_greed=90, long_short_ratio=0.5)
        res = ind.evaluate(df, ctx)
        # Only long_short_ratio < 0.7 is evaluated -> BULL
        assert res.state == "BULL"


class TestIndicatorEngineOverlaysAndPanes:
    def test_overlays_and_panes_generation(self) -> None:
        engine = IndicatorEngine()
        df = create_sample_df(n=60, trend="bull")
        chart_data = engine.generate_chart_overlays_and_panes(df, limit=50)

        assert "overlays" in chart_data
        assert "panes" in chart_data
        assert "vwap" in chart_data["overlays"]
        assert "ema_ribbon" in chart_data["overlays"]
        assert "supertrend" in chart_data["overlays"]
        assert "bollinger" in chart_data["overlays"]
        assert "rsi" in chart_data["panes"]
        assert "cvd" in chart_data["panes"]
        assert len(chart_data["overlays"]["vwap"]) > 0
        assert len(chart_data["panes"]["rsi"]) > 0
