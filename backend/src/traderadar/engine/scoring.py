"""Confluence scoring, category voting, and verdict determination."""

from typing import Literal

from pydantic import BaseModel, Field

from traderadar.engine.indicators.base import IndicatorResult

VerdictType = Literal["STRONG_LONG", "LONG", "NEUTRAL", "SHORT", "STRONG_SHORT"]
H1BiasType = Literal["BULL", "BEAR", "NEUTRAL"]

DEFAULT_WEIGHTS: dict[str, float] = {
    "ema_ribbon": 12.0,
    "supertrend": 13.0,
    "rsi_div": 8.0,
    "bollinger": 7.0,
    "vwap": 12.0,
    "cvd_obv": 13.0,
    "funding_oi": 10.0,
    "orderbook": 5.0,
    "lightgbm": 15.0,
    "sentiment": 5.0,
}


class ConfluenceScoreResult(BaseModel):
    """Complete result of confluence calculation."""

    score: float = Field(ge=-100.0, le=100.0)
    verdict: VerdictType
    counts: dict[str, int]
    category_votes: dict[str, str]
    available_weight: float
    total_weight: float
    available_weight_pct: float
    h1_confirmation: H1BiasType
    macro_passed: bool


def evaluate_h1_confirmation(
    ema_ribbon_state: str,
    supertrend_state: str,
    rsi_value: float | None = None,
) -> H1BiasType:
    """Evaluate H1 multi-indicator confirmation.

    Majority of {EMA Ribbon H1, Supertrend H1, RSI H1 side of 50}.
    """
    votes: list[int] = []

    # 1. EMA Ribbon H1
    if ema_ribbon_state == "BULL":
        votes.append(1)
    elif ema_ribbon_state == "BEAR":
        votes.append(-1)
    else:
        votes.append(0)

    # 2. Supertrend H1
    if supertrend_state == "BULL":
        votes.append(1)
    elif supertrend_state == "BEAR":
        votes.append(-1)
    else:
        votes.append(0)

    # 3. RSI H1 side of 50
    if rsi_value is not None:
        if rsi_value > 50.0:
            votes.append(1)
        elif rsi_value < 50.0:
            votes.append(-1)
        else:
            votes.append(0)
    else:
        votes.append(0)

    total = sum(votes)
    if total > 0:
        return "BULL"
    elif total < 0:
        return "BEAR"
    return "NEUTRAL"


def calculate_confluence_score(
    indicators: list[IndicatorResult],
    weights: dict[str, float] | None = None,
    h1_confirmation: H1BiasType = "NEUTRAL",
    macro_passed: bool = True,
    strong_score: float = 55.0,
    watch_score: float = 30.0,
    min_categories: int = 3,
    min_available_weight_pct: float = 50.0,
) -> ConfluenceScoreResult:
    """Calculate normalized confluence score (-100 to +100), category votes, and verdict.

    Formula from SIGNAL_ENGINE.md §4:
    s_i = +1 (BULL) | -1 (BEAR) | 0 (NEUTRAL); NA is dropped.
    score = 100 * sum(w_i * s_i * strength_i) / sum(w_i)  [sum over available indicators]
    """
    active_weights = weights if weights is not None else DEFAULT_WEIGHTS
    total_weight = sum(active_weights.values())

    counts: dict[str, int] = {"BULL": 0, "BEAR": 0, "NEUTRAL": 0, "NA": 0}
    category_scores: dict[str, float] = {
        "trend": 0.0,
        "momentum": 0.0,
        "order_flow": 0.0,
        "derivatives": 0.0,
        "microstructure": 0.0,
        "ml": 0.0,
        "sentiment": 0.0,
    }

    numerator = 0.0
    available_weight = 0.0

    for ind in indicators:
        st = ind.state
        counts[st] = counts.get(st, 0) + 1

        if st == "NA":
            continue

        w = active_weights.get(ind.key, 0.0)
        s_i = 1.0 if st == "BULL" else (-1.0 if st == "BEAR" else 0.0)
        contrib = w * s_i * ind.strength

        numerator += contrib
        available_weight += w

        if ind.category in category_scores:
            category_scores[ind.category] += contrib

    # Normalization
    if available_weight > 0:
        raw_score = 100.0 * (numerator / available_weight)
        score = max(-100.0, min(100.0, round(raw_score, 2)))
        available_weight_pct = (
            round((available_weight / total_weight) * 100.0, 2) if total_weight > 0 else 0.0
        )
    else:
        score = 0.0
        available_weight_pct = 0.0

    # Category votes: > 0 => BULL, < 0 => BEAR, == 0 => NEUTRAL
    category_votes: dict[str, str] = {}
    bull_categories = 0
    bear_categories = 0
    for cat, val in category_scores.items():
        if val > 1e-4:
            category_votes[cat] = "BULL"
            bull_categories += 1
        elif val < -1e-4:
            category_votes[cat] = "BEAR"
            bear_categories += 1
        else:
            category_votes[cat] = "NEUTRAL"

    trend_category = category_votes.get("trend", "NEUTRAL")
    can_be_strong = available_weight_pct >= min_available_weight_pct

    # Verdict evaluation
    verdict: VerdictType = "NEUTRAL"

    if (
        score >= strong_score
        and bull_categories >= min_categories
        and trend_category == "BULL"
        and h1_confirmation != "BEAR"
        and macro_passed
        and can_be_strong
    ):
        verdict = "STRONG_LONG"
    elif (
        score <= -strong_score
        and bear_categories >= min_categories
        and trend_category == "BEAR"
        and h1_confirmation != "BULL"
        and macro_passed
        and can_be_strong
    ):
        verdict = "STRONG_SHORT"
    elif score >= watch_score and trend_category != "BEAR":
        verdict = "LONG"
    elif score <= -watch_score and trend_category != "BULL":
        verdict = "SHORT"
    else:
        verdict = "NEUTRAL"

    return ConfluenceScoreResult(
        score=score,
        verdict=verdict,
        counts=counts,
        category_votes=category_votes,
        available_weight=available_weight,
        total_weight=total_weight,
        available_weight_pct=available_weight_pct,
        h1_confirmation=h1_confirmation,
        macro_passed=macro_passed,
    )
