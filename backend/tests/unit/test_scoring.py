"""Unit tests for confluence scoring, weight normalization, and verdict logic."""

from traderadar.engine.indicators.base import IndicatorResult
from traderadar.engine.scoring import (
    DEFAULT_WEIGHTS,
    calculate_confluence_score,
    evaluate_h1_confirmation,
)


def _make_dummy_indicators(states: dict[str, tuple[str, float]]) -> list[IndicatorResult]:
    """Helper to construct indicator results list.

    states: {key: (state, strength)}
    """
    category_map = {
        "vwap": "order_flow",
        "ema_ribbon": "trend",
        "supertrend": "trend",
        "rsi_div": "momentum",
        "bollinger": "momentum",
        "cvd_obv": "order_flow",
        "funding_oi": "derivatives",
        "orderbook": "microstructure",
        "lightgbm": "ml",
        "sentiment": "sentiment",
    }
    results = []
    for key, (st, strg) in states.items():
        cat = category_map.get(key, "trend")
        results.append(
            IndicatorResult(
                key=key,
                category=cat,
                state=st,
                strength=strg,
                values={},
                reason=f"Test indicator {key}",
            )
        )
    return results


def test_scoring_all_bull_reaches_100() -> None:
    """When all indicators are BULL with strength 1.0, score must be 100 and verdict STRONG_LONG."""
    states = dict.fromkeys(DEFAULT_WEIGHTS.keys(), ("BULL", 1.0))
    indicators = _make_dummy_indicators(states)

    res = calculate_confluence_score(
        indicators=indicators,
        h1_confirmation="BULL",
        macro_passed=True,
    )

    assert res.score == 100.0
    assert res.verdict == "STRONG_LONG"
    assert res.counts["BULL"] == 10
    assert res.counts["BEAR"] == 0
    assert res.available_weight_pct == 100.0
    assert res.category_votes["trend"] == "BULL"
    assert res.category_votes["momentum"] == "BULL"


def test_scoring_all_bear_reaches_minus_100() -> None:
    """When all indicators are BEAR with strength 1.0, score must be -100."""
    states = dict.fromkeys(DEFAULT_WEIGHTS.keys(), ("BEAR", 1.0))
    indicators = _make_dummy_indicators(states)

    res = calculate_confluence_score(
        indicators=indicators,
        h1_confirmation="BEAR",
        macro_passed=True,
    )

    assert res.score == -100.0
    assert res.verdict == "STRONG_SHORT"
    assert res.counts["BEAR"] == 10
    assert res.category_votes["trend"] == "BEAR"


def test_scoring_na_is_discarded_from_weights() -> None:
    """Indicators with state 'NA' must be removed from both numerator and denominator."""
    # Only 2 indicators available: ema_ribbon (12) BULL, supertrend (13) BULL. Others NA.
    states = {
        "ema_ribbon": ("BULL", 1.0),
        "supertrend": ("BULL", 1.0),
        "vwap": ("NA", 0.0),
        "rsi_div": ("NA", 0.0),
        "bollinger": ("NA", 0.0),
        "cvd_obv": ("NA", 0.0),
        "funding_oi": ("NA", 0.0),
        "orderbook": ("NA", 0.0),
        "lightgbm": ("NA", 0.0),
        "sentiment": ("NA", 0.0),
    }
    indicators = _make_dummy_indicators(states)

    res = calculate_confluence_score(
        indicators=indicators,
        h1_confirmation="BULL",
        macro_passed=True,
    )

    # Score of available (12*1 + 13*1) / (12 + 13) = 25/25 = 100.0
    assert res.score == 100.0
    assert res.available_weight == 25.0
    assert res.available_weight_pct == 25.0
    # Because available_weight_pct (25%) < 50%, cannot be STRONG!
    assert res.verdict != "STRONG_LONG"
    # But can be watch LONG
    assert res.verdict == "LONG"


def test_scoring_macro_failed_prevents_strong_verdict() -> None:
    """When macro filter fails (macro_passed=False), strong signals are blocked/downgraded."""
    states = dict.fromkeys(DEFAULT_WEIGHTS.keys(), ("BULL", 1.0))
    indicators = _make_dummy_indicators(states)

    res = calculate_confluence_score(
        indicators=indicators,
        h1_confirmation="BULL",
        macro_passed=False,  # Blocked by macro filter
    )

    assert res.score == 100.0
    # Must NOT be STRONG_LONG
    assert res.verdict != "STRONG_LONG"
    assert res.verdict == "LONG"


def test_scoring_h1_bear_prevents_strong_long() -> None:
    """If H1 confirmation is BEAR, STRONG_LONG must not be given."""
    states = dict.fromkeys(DEFAULT_WEIGHTS.keys(), ("BULL", 1.0))
    indicators = _make_dummy_indicators(states)

    res = calculate_confluence_score(
        indicators=indicators,
        h1_confirmation="BEAR",
        macro_passed=True,
    )

    assert res.score == 100.0
    assert res.verdict != "STRONG_LONG"
    assert res.verdict == "LONG"


def test_evaluate_h1_confirmation() -> None:
    """Test multi-indicator majority vote for H1 confirmation."""
    # 2 Bull (Ribbon, ST) + 1 Bear (RSI) => BULL
    assert evaluate_h1_confirmation("BULL", "BULL", rsi_value=40.0) == "BULL"
    # 2 Bear (ST, RSI < 50) + 1 Neutral (Ribbon) => BEAR
    assert evaluate_h1_confirmation("NEUTRAL", "BEAR", rsi_value=45.0) == "BEAR"
    # Tie / all Neutral => NEUTRAL
    assert evaluate_h1_confirmation("NEUTRAL", "NEUTRAL", rsi_value=50.0) == "NEUTRAL"
