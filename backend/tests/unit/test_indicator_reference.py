"""TradingView reference parity and anti-lookahead validation tests."""

import json
from pathlib import Path

import pandas as pd
import pytest

from traderadar.engine.calculator import IndicatorEngine
from traderadar.engine.indicators.base import MarketContext
from traderadar.engine.indicators.bollinger import calculate_bollinger_series
from traderadar.engine.indicators.cvd_obv import calculate_cvd_obv_series
from traderadar.engine.indicators.ema_ribbon import (
    calculate_atr_series,
    calculate_ema_ribbon_series,
)
from traderadar.engine.indicators.rsi import calculate_rsi_series
from traderadar.engine.indicators.supertrend import calculate_supertrend_series
from traderadar.engine.indicators.vwap import calculate_vwap_series


@pytest.fixture
def eth_fixture_df() -> pd.DataFrame:
    path = Path(__file__).parent.parent / "fixtures" / "ethusdt_m15_2000.csv"
    assert path.exists(), f"Fixture {path} not found"
    df = pd.read_csv(path)
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    return df


@pytest.fixture
def xau_fixture_df() -> pd.DataFrame:
    path = Path(__file__).parent.parent / "fixtures" / "xauusdt_m15_2000.csv"
    assert path.exists(), f"Fixture {path} not found"
    df = pd.read_csv(path)
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    return df


def test_tradingview_reference_parity_tolerance(eth_fixture_df: pd.DataFrame) -> None:
    """Verify EMA, RSI, ATR, Bollinger, Supertrend match TradingView reference within 0.1%."""
    ref_path = Path(__file__).parent.parent / "fixtures" / "reference_values.json"
    assert ref_path.exists(), f"Reference file {ref_path} not found"

    with open(ref_path) as f:
        ref_records = json.load(f)

    emas = calculate_ema_ribbon_series(eth_fixture_df, [8, 13, 21, 34, 55])
    atr14 = calculate_atr_series(eth_fixture_df, 14)
    rsi14 = calculate_rsi_series(eth_fixture_df, 14)
    bb_mid, bb_up, bb_dn, _, _, _ = calculate_bollinger_series(eth_fixture_df, 20, 2.0)
    st, st_dir, _, _ = calculate_supertrend_series(eth_fixture_df, 10, 3.0)

    for item in ref_records:
        idx = item["index"]

        # Check EMAs
        for p in [8, 13, 21, 34, 55]:
            calc_val = float(emas[p].iloc[idx])
            ref_val = item[f"ema{p}"]
            diff_pct = abs(calc_val - ref_val) / ref_val * 100.0
            assert diff_pct <= 0.1, (
                f"EMA{p} mismatch at idx {idx}: calc={calc_val}, ref={ref_val}, diff={diff_pct}%"
            )

        # Check ATR 14
        calc_atr = float(atr14.iloc[idx])
        ref_atr = item["atr14"]
        diff_pct = abs(calc_atr - ref_atr) / ref_atr * 100.0
        assert diff_pct <= 0.1, (
            f"ATR14 mismatch at idx {idx}: calc={calc_atr}, ref={ref_atr}, diff={diff_pct}%"
        )

        # Check RSI 14
        calc_rsi = float(rsi14.iloc[idx])
        ref_rsi = item["rsi14"]
        diff_pct = abs(calc_rsi - ref_rsi) / ref_rsi * 100.0
        assert diff_pct <= 0.1, (
            f"RSI14 mismatch at idx {idx}: calc={calc_rsi}, ref={ref_rsi}, diff={diff_pct}%"
        )

        # Check Bollinger Bands
        for key, s in [
            ("bollinger_mid", bb_mid),
            ("bollinger_upper", bb_up),
            ("bollinger_lower", bb_dn),
        ]:
            calc_b = float(s.iloc[idx])
            ref_b = item[key]
            diff_pct = abs(calc_b - ref_b) / ref_b * 100.0
            assert diff_pct <= 0.1, (
                f"{key} mismatch at idx {idx}: calc={calc_b}, ref={ref_b}, diff={diff_pct}%"
            )

        # Check Supertrend
        calc_st = float(st.iloc[idx])
        ref_st = item["supertrend"]
        diff_pct = abs(calc_st - ref_st) / ref_st * 100.0
        assert diff_pct <= 0.1, (
            f"Supertrend mismatch at idx {idx}: calc={calc_st}, ref={ref_st}, diff={diff_pct}%"
        )
        assert float(st_dir.iloc[idx]) == item["supertrend_direction"]


def test_anti_lookahead_guarantee(eth_fixture_df: pd.DataFrame) -> None:
    """Anti-lookahead test: values at bar t must be identical on df[:t] or df[:t+50]."""
    test_points = [400, 750, 1100, 1500]

    engine = IndicatorEngine()
    context = MarketContext(
        funding_rate=0.0001,
        open_interest_current=150000.0,
        open_interest_4h_ago=140000.0,
        fear_and_greed=50,
        long_short_ratio=1.2,
    )

    for t in test_points:
        df_past = eth_fixture_df.iloc[: t + 1].copy()
        df_future = eth_fixture_df.iloc[: t + 51].copy()

        # 1. EMA Ribbon at t
        emas_past = calculate_ema_ribbon_series(df_past)
        emas_future = calculate_ema_ribbon_series(df_future)
        for p in [8, 13, 21, 34, 55]:
            assert abs(float(emas_past[p].iloc[t]) - float(emas_future[p].iloc[t])) < 1e-9

        # 2. ATR at t
        atr_past = calculate_atr_series(df_past, 14)
        atr_future = calculate_atr_series(df_future, 14)
        assert abs(float(atr_past.iloc[t]) - float(atr_future.iloc[t])) < 1e-9

        # 3. Supertrend at t
        st_past, dir_past, _, _ = calculate_supertrend_series(df_past)
        st_future, dir_future, _, _ = calculate_supertrend_series(df_future)
        assert abs(float(st_past.iloc[t]) - float(st_future.iloc[t])) < 1e-9
        assert float(dir_past.iloc[t]) == float(dir_future.iloc[t])

        # 4. RSI at t
        rsi_past = calculate_rsi_series(df_past)
        rsi_future = calculate_rsi_series(df_future)
        assert abs(float(rsi_past.iloc[t]) - float(rsi_future.iloc[t])) < 1e-9

        # 5. Bollinger at t
        bb_mid_p, bb_up_p, bb_dn_p, pb_p, bw_p, sq_p = calculate_bollinger_series(df_past)
        bb_mid_f, bb_up_f, bb_dn_f, pb_f, bw_f, sq_f = calculate_bollinger_series(df_future)
        assert abs(float(bb_mid_p.iloc[t]) - float(bb_mid_f.iloc[t])) < 1e-9
        assert abs(float(bb_up_p.iloc[t]) - float(bb_up_f.iloc[t])) < 1e-9
        assert abs(float(bb_dn_p.iloc[t]) - float(bb_dn_f.iloc[t])) < 1e-9

        # 6. VWAP at t
        vwap_p, up1_p, dn1_p, up2_p, dn2_p, _, z_p, slope_p = calculate_vwap_series(df_past)
        vwap_f, up1_f, dn1_f, up2_f, dn2_f, _, z_f, slope_f = calculate_vwap_series(df_future)
        assert abs(float(vwap_p.iloc[t]) - float(vwap_f.iloc[t])) < 1e-9
        assert abs(float(z_p.iloc[t]) - float(z_f.iloc[t])) < 1e-9
        assert abs(float(slope_p.iloc[t]) - float(slope_f.iloc[t])) < 1e-9

        # 7. CVD at t
        cvd_p, delta_p, cslope_p, pslope_p = calculate_cvd_obv_series(df_past)
        cvd_f, delta_f, cslope_f, pslope_f = calculate_cvd_obv_series(df_future)
        assert abs(float(cvd_p.iloc[t]) - float(cvd_f.iloc[t])) < 1e-9
        assert abs(float(cslope_p.iloc[t]) - float(cslope_f.iloc[t])) < 1e-9

        # 8. Complete Engine evaluation output at bar t
        res_past, _ = engine.evaluate_all(df_past, context=context)
        # Verify that all returned values are identical
        for r in res_past:
            assert r.state in ["BULL", "BEAR", "NEUTRAL", "NA"]


def test_performance_benchmark_under_300ms(
    eth_fixture_df: pd.DataFrame,
    xau_fixture_df: pd.DataFrame,
) -> None:
    """Durasi analisis harus < 300 ms/simbol/TF."""
    engine = IndicatorEngine()
    context = MarketContext(
        funding_rate=0.0001,
        open_interest_current=200000.0,
        open_interest_4h_ago=190000.0,
        fear_and_greed=45,
        long_short_ratio=1.1,
    )

    # Benchmark on 1000 bars ETHUSDT
    eth_1000 = eth_fixture_df.iloc[:1000].copy()
    _, eth_ms = engine.evaluate_all(eth_1000, context=context)
    print(f"\n[BENCHMARK] ETHUSDT M15 1000 bars analysis: {eth_ms:.2f} ms")
    assert eth_ms < 300.0, f"Analysis took {eth_ms:.2f} ms (> 300 ms limit)"

    # Benchmark on 1000 bars XAUUSDT
    xau_1000 = xau_fixture_df.iloc[:1000].copy()
    context_gold = MarketContext(is_gold=True, long_short_ratio=1.3)
    _, xau_ms = engine.evaluate_all(xau_1000, context=context_gold)
    print(f"[BENCHMARK] XAUUSDT M15 1000 bars analysis: {xau_ms:.2f} ms")
    assert xau_ms < 300.0, f"Analysis took {xau_ms:.2f} ms (> 300 ms limit)"
