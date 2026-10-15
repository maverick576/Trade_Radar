"""Triple-EMA Strategy (Strategy B) adapted from Ruang Scalper."""

from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel

from traderadar.core.config import StrategyBTripleEmaSettings
from traderadar.engine.macro_filter import MacroFilterResult


class StrategyBResult(BaseModel):
    """Output evaluation of Triple-EMA Strategy B."""

    state: Literal["LONG", "SHORT", "NEUTRAL"]
    entry: float | None = None
    sl: float | None = None
    tp: float | None = None
    rr: float = 1.0
    confirmed: bool = False
    reason: str = ""


def evaluate_triple_ema(
    df_m15: pd.DataFrame,
    df_h1: pd.DataFrame | None = None,
    macro_result: MacroFilterResult | None = None,
    settings: StrategyBTripleEmaSettings | None = None,
) -> StrategyBResult:
    """Evaluate Strategy B on M15 close with H1 trend confirmation."""
    cfg = settings or StrategyBTripleEmaSettings()

    if not cfg.enabled or len(df_m15) < 55:
        return StrategyBResult(
            state="NEUTRAL",
            reason="Data candle tidak cukup atau Strategi B dinonaktifkan",
        )

    # 1. Calculate EMAs on M15
    close_m15 = df_m15["close"].astype(float)
    open_m15 = df_m15["open"].astype(float)
    high_m15 = df_m15["high"].astype(float)
    low_m15 = df_m15["low"].astype(float)

    ema_fast = close_m15.ewm(span=cfg.fast, adjust=False).mean()
    ema_mid = (
        open_m15.ewm(span=cfg.mid, adjust=False).mean()
        if cfg.mid_source == "open"
        else close_m15.ewm(span=cfg.mid, adjust=False).mean()
    )
    ema_slow = close_m15.ewm(span=cfg.slow, adjust=False).mean()

    # 2. Check crossover at bar t (index -1) vs bar t-1 (index -2)
    fast_t, fast_prev = float(ema_fast.iloc[-1]), float(ema_fast.iloc[-2])
    mid_t, mid_prev = float(ema_mid.iloc[-1]), float(ema_mid.iloc[-2])
    slow_t = float(ema_slow.iloc[-1])
    slow_5_ago = float(ema_slow.iloc[-6]) if len(df_m15) >= 6 else slow_t
    close_t = float(close_m15.iloc[-1])

    bull_cross = (fast_t > mid_t) and (fast_prev <= mid_prev)
    bear_cross = (fast_t < mid_t) and (fast_prev >= mid_prev)

    slow_slope_up = slow_t > slow_5_ago
    slow_slope_down = slow_t < slow_5_ago

    # 3. H1 Trend Confirmation: EMA9 > EMA21 > EMA50
    h1_bull = True
    h1_bear = True
    if df_h1 is not None and len(df_h1) >= 55:
        close_h1 = df_h1["close"].astype(float)
        ema9_h1 = close_h1.ewm(span=cfg.fast, adjust=False).mean().iloc[-1]
        ema21_h1 = close_h1.ewm(span=cfg.mid, adjust=False).mean().iloc[-1]
        ema50_h1 = close_h1.ewm(span=cfg.slow, adjust=False).mean().iloc[-1]

        h1_bull = bool(ema9_h1 > ema21_h1 > ema50_h1)
        h1_bear = bool(ema9_h1 < ema21_h1 < ema50_h1)

    # 4. Check ATR for Risk & Exit levels
    # Wilder ATR 14
    tr1 = high_m15 - low_m15
    tr2 = (high_m15 - close_m15.shift(1)).abs()
    tr3 = (low_m15 - close_m15.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr14 = float(tr.ewm(alpha=1.0 / 14.0, adjust=False).mean().iloc[-1])
    if atr14 <= 0 or np.isnan(atr14):
        atr14 = close_t * 0.005

    swing_low_10 = float(low_m15.iloc[-10:].min())
    swing_high_10 = float(high_m15.iloc[-10:].max())

    # 5. Evaluate state
    candidate_state: Literal["LONG", "SHORT", "NEUTRAL"] = "NEUTRAL"
    reason = ""

    if bull_cross and (close_t > slow_t) and slow_slope_up and h1_bull:
        candidate_state = "LONG"
        reason = (
            f"Cross EMA{cfg.fast} di atas EMA{cfg.mid}(open), close > EMA{cfg.slow}, dan H1 bullish"
        )
    elif bear_cross and (close_t < slow_t) and slow_slope_down and h1_bear:
        candidate_state = "SHORT"
        reason = (
            f"Cross EMA{cfg.fast} di bawah EMA{cfg.mid}(open), "
            f"close < EMA{cfg.slow}, dan H1 bearish"
        )
    else:
        return StrategyBResult(
            state="NEUTRAL",
            reason="Tidak ada setup crossover Triple-EMA valid",
        )

    # 6. SL and TP calculation
    entry = close_t
    rr_target = cfg.rr_target

    if candidate_state == "LONG":
        dist_swing = entry - swing_low_10
        dist_atr = 1.2 * atr14
        chosen_dist = min(dist_swing, dist_atr)
        # Clamped: distance >= 0.8 * ATR
        risk_dist = max(chosen_dist, 0.8 * atr14)
        sl = round(entry - risk_dist, 4)
        tp = round(entry + (risk_dist * rr_target), 4)
    else:
        dist_swing = swing_high_10 - entry
        dist_atr = 1.2 * atr14
        chosen_dist = min(dist_swing, dist_atr)
        risk_dist = max(chosen_dist, 0.8 * atr14)
        sl = round(entry + risk_dist, 4)
        tp = round(entry - (risk_dist * rr_target), 4)

    # 7. Check Macro Filters M2–M6
    macro_passed = True
    blocked_reasons: list[str] = []
    if macro_result is not None:
        for chk in macro_result.checks:
            if chk.id in ("M2", "M3", "M4", "M5", "M6") and not chk.passed:
                macro_passed = False
                blocked_reasons.append(f"{chk.id}: {chk.detail}")

    if not macro_passed:
        reason += f" [Terblokir filter: {'; '.join(blocked_reasons)}]"

    return StrategyBResult(
        state=candidate_state,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr_target,
        confirmed=macro_passed,
        reason=reason,
    )
