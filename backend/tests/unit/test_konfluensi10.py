"""Integration tests for ConfluencePipeline (Strategy A & B end-to-end)."""

from pathlib import Path

import pandas as pd
import pytest

from traderadar.engine.strategies.konfluensi10 import ConfluencePipeline


@pytest.fixture
def eth_candles() -> pd.DataFrame:
    """Load historical ETHUSDT M15 fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "ethusdt_m15_2000.csv"
    if not fixture_path.exists():
        pytest.skip("ETHUSDT fixture not present")
    df = pd.read_csv(fixture_path)
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    return df


def test_pipeline_runs_successfully(eth_candles: pd.DataFrame) -> None:
    """Pipeline evaluates 10 indicators, scoring, macro, and produces an Analysis object."""
    pipeline = ConfluencePipeline()
    sample = eth_candles.iloc[:300].copy()

    analysis, signals = pipeline.run_analysis(
        symbol="ETHUSDT",
        tf="M15",
        source="binance_futures:ETHUSDT",
        df_m15=sample,
        df_h1=None,
        df_h4=None,
        df_d1=None,
    )

    assert analysis.symbol == "ETHUSDT"
    assert analysis.tf == "M15"
    assert len(analysis.indicators) == 10
    assert -100.0 <= analysis.score <= 100.0
    assert analysis.verdict in ("STRONG_LONG", "LONG", "NEUTRAL", "SHORT", "STRONG_SHORT")
    assert isinstance(analysis.macro.passed, bool)
    assert len(analysis.macro.checks) == 8


def test_pipeline_cooldown_downgrade(eth_candles: pd.DataFrame) -> None:
    """When previous strong signal was recent (<= 4 bars), signal is not duplicate strong."""
    pipeline = ConfluencePipeline()
    sample = eth_candles.iloc[:300].copy()

    # Artificially test cooldown logic
    analysis, signals = pipeline.run_analysis(
        symbol="ETHUSDT",
        tf="M15",
        source="binance_futures:ETHUSDT",
        df_m15=sample,
        previous_signal_side="LONG",
        previous_signal_bars_ago=2,  # <= 4 bars ago
    )

    # Even if score is high, it cannot be duplicate STRONG_LONG
    assert analysis.verdict != "STRONG_LONG"
