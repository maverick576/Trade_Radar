"""Macro filter evaluation (M1-M8) according to SIGNAL_ENGINE.md §5."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from traderadar.core.config import MacroFilterSettings
from traderadar.core.time import is_gold_market_open, is_gold_rollover


class MacroCheck(BaseModel):
    """Result of an individual macro filter rule."""

    id: str  # M1..M8
    name: str
    passed: bool
    detail: str


class MacroFilterResult(BaseModel):
    """Consolidated result of all macro filter checks."""

    passed: bool
    checks: list[MacroCheck] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)


class MacroFilterContext(BaseModel):
    """Context required to evaluate all 8 macro filter checks."""

    symbol: str
    side: Literal["LONG", "SHORT", "NEUTRAL"]
    bar_time: datetime

    # M1: HTF Trend
    h4_close: float | None = None
    h4_ema200: float | None = None
    d1_supertrend_dir: float | None = None  # +1.0 BULL, -1.0 BEAR

    # M2: News
    has_news_event_nearby: bool = False
    nearby_news_detail: str | None = None

    # M3: Volatility ATR
    current_atr: float | None = None
    atr_p10: float | None = None
    atr_p95: float | None = None

    # M4: Gold Session
    is_gold: bool = False

    # M5: Liquidity Spread
    current_spread: float | None = None
    median_spread_24h: float | None = None

    # M6: Data Freshness
    candle_age_seconds: float = 0.0
    tf_seconds: float = 900.0  # M15 default = 15*60
    ws_connected: bool = True
    is_fallback_gold: bool = False
    fallback_active_minutes: float = 999.0

    # M7: Extreme Funding (crypto)
    funding_rate: float | None = None

    # M8: Risk Paper
    daily_loss_limit_reached: bool = False
    has_open_position_for_symbol: bool = False


def evaluate_macro_filters(
    ctx: MacroFilterContext,
    settings: MacroFilterSettings | None = None,
) -> MacroFilterResult:
    """Evaluate checks M1 through M8 against the provided market context."""
    cfg = settings or MacroFilterSettings()
    checks: list[MacroCheck] = []

    # -------------------------------------------------------------
    # M1: Tren Besar (H4 close vs EMA200 H4, Supertrend D1)
    # Gagal bila KEDUA-DUANYA berlawanan dengan arah sinyal
    # -------------------------------------------------------------
    m1_passed = True
    m1_detail = "Tren besar sejalan atau netral"

    if ctx.side in ("LONG", "SHORT"):
        h4_opposes = False
        d1_opposes = False

        if ctx.h4_close is not None and ctx.h4_ema200 is not None:
            if ctx.side == "LONG" and ctx.h4_close < ctx.h4_ema200:
                h4_opposes = True
            elif ctx.side == "SHORT" and ctx.h4_close > ctx.h4_ema200:
                h4_opposes = True

        if ctx.d1_supertrend_dir is not None:
            if ctx.side == "LONG" and ctx.d1_supertrend_dir < 0:
                d1_opposes = True
            elif ctx.side == "SHORT" and ctx.d1_supertrend_dir > 0:
                d1_opposes = True

        if h4_opposes and d1_opposes:
            m1_passed = False
            m1_detail = (
                f"Sinyal {ctx.side} berlawanan dengan H4 (< EMA200) dan Supertrend D1"
                if ctx.side == "LONG"
                else f"Sinyal {ctx.side} berlawanan dengan H4 (> EMA200) dan Supertrend D1"
            )
        elif h4_opposes:
            m1_detail = f"H4 berlawanan tapi D1 mendukung sinyal {ctx.side}"
        elif d1_opposes:
            m1_detail = f"D1 berlawanan tapi H4 mendukung sinyal {ctx.side}"
        else:
            m1_detail = f"H4 dan D1 mengonfirmasi bias {ctx.side}"
    else:
        m1_detail = "Sinyal netral, lolos cek tren besar"

    checks.append(MacroCheck(id="M1", name="Tren Besar (HTF)", passed=m1_passed, detail=m1_detail))

    # -------------------------------------------------------------
    # M2: Berita High-Impact (-30 / +30 menit)
    # -------------------------------------------------------------
    m2_passed = not ctx.has_news_event_nearby
    m2_detail = (
        f"Event USD High-impact terdeteksi ({ctx.nearby_news_detail or 'dalam jendela ±30m'})"
        if not m2_passed
        else "Tidak ada rilis berita USD berdampak tinggi dalam ±30 menit"
    )
    checks.append(
        MacroCheck(id="M2", name="Berita High-Impact", passed=m2_passed, detail=m2_detail)
    )

    # -------------------------------------------------------------
    # M3: Volatilitas (ATR14 M15 vs P10 / P95)
    # -------------------------------------------------------------
    m3_passed = True
    m3_detail = "Volatilitas ATR normal di antara P10 dan P95"
    if ctx.current_atr is not None and ctx.atr_p10 is not None and ctx.atr_p95 is not None:
        if ctx.current_atr < ctx.atr_p10:
            m3_passed = False
            m3_detail = (
                f"ATR ({ctx.current_atr:.2f}) < P10 ({ctx.atr_p10:.2f}) "
                "— pasar mati/likuiditas rendah"
            )
        elif ctx.current_atr > ctx.atr_p95:
            m3_passed = False
            m3_detail = (
                f"ATR ({ctx.current_atr:.2f}) > P95 ({ctx.atr_p95:.2f}) — volatilitas ekstrem/liar"
            )
    checks.append(MacroCheck(id="M3", name="Volatilitas ATR", passed=m3_passed, detail=m3_detail))

    # -------------------------------------------------------------
    # M4: Sesi Pasar (Khusus Gold)
    # Pasar tutup (Jumat 21:00 UTC - Minggu 22:00 UTC) atau rollover 20:45-01:15 UTC
    # -------------------------------------------------------------
    m4_passed = True
    m4_detail = "Bukan instrumen Gold atau sesi pasar buka normal"
    if ctx.is_gold:
        rollover_start = cfg.gold_rollover_utc[0] if len(cfg.gold_rollover_utc) > 0 else "20:45"
        rollover_end = cfg.gold_rollover_utc[1] if len(cfg.gold_rollover_utc) > 1 else "01:15"

        is_open = is_gold_market_open(ctx.bar_time)
        is_roll = is_gold_rollover(ctx.bar_time, start_utc=rollover_start, end_utc=rollover_end)

        if not is_open:
            m4_passed = False
            m4_detail = "Pasar fisik emas (TradFi) tutup akhir pekan atau jeda harian"
        elif is_roll:
            m4_passed = False
            m4_detail = (
                f"Jendela rollover spread broker melebar ({rollover_start} - {rollover_end} UTC)"
            )
        else:
            m4_detail = "Pasar emas buka dan di luar jam rollover spread"

    checks.append(MacroCheck(id="M4", name="Sesi Pasar Gold", passed=m4_passed, detail=m4_detail))

    # -------------------------------------------------------------
    # M5: Likuiditas (Spread > 2x median 24h)
    # -------------------------------------------------------------
    m5_passed = True
    m5_detail = "Likuiditas spread orderbook normal"
    if (
        ctx.current_spread is not None
        and ctx.median_spread_24h is not None
        and ctx.median_spread_24h > 0
    ):
        multiplier = cfg.spread_median_multiplier
        if ctx.current_spread > multiplier * ctx.median_spread_24h:
            m5_passed = False
            m5_detail = (
                f"Spread saat ini ({ctx.current_spread:.4f}) > {multiplier}x "
                f"median 24j ({ctx.median_spread_24h:.4f}) — pasar tipis"
            )
    checks.append(MacroCheck(id="M5", name="Likuiditas Spread", passed=m5_passed, detail=m5_detail))

    # -------------------------------------------------------------
    # M6: Kesegaran Data (> 2x TF, WS putus, fallback < 60m)
    # -------------------------------------------------------------
    m6_passed = True
    m6_detail = "Data candle segar dan koneksi websocket lancar"

    if not ctx.ws_connected:
        m6_passed = False
        m6_detail = "Koneksi WebSocket terputus, data real-time tidak terjamin"
    elif ctx.candle_age_seconds > 2 * ctx.tf_seconds:
        m6_passed = False
        m6_detail = (
            f"Keterlambatan candle ({int(ctx.candle_age_seconds)}s) > "
            f"2x durasi TF ({int(ctx.tf_seconds)}s)"
        )
    elif (
        ctx.is_gold
        and ctx.is_fallback_gold
        and ctx.fallback_active_minutes < cfg.fallback_warmup_minutes
    ):
        m6_passed = False
        m6_detail = (
            f"Sumber fallback Gold baru aktif {int(ctx.fallback_active_minutes)}m "
            f"(butuh pemanasan ≥ {cfg.fallback_warmup_minutes}m)"
        )

    checks.append(MacroCheck(id="M6", name="Kesegaran Data", passed=m6_passed, detail=m6_detail))

    # -------------------------------------------------------------
    # M7: Funding Ekstrem (|funding| > 0.1% per 8 jam)
    # -------------------------------------------------------------
    m7_passed = True
    m7_detail = "Funding rate dalam batas wajar"
    if ctx.funding_rate is not None:
        if abs(ctx.funding_rate) > cfg.max_funding_abs:
            m7_passed = False
            pct_val = ctx.funding_rate * 100.0
            m7_detail = (
                f"Funding rate ekstrem ({pct_val:+.3f}% per 8j > "
                f"±{cfg.max_funding_abs * 100:.2f}%) — risiko short/long squeeze"
            )
        else:
            m7_detail = f"Funding rate {ctx.funding_rate * 100:+.3f}% per 8j (wajar)"

    checks.append(MacroCheck(id="M7", name="Funding Ekstrem", passed=m7_passed, detail=m7_detail))

    # -------------------------------------------------------------
    # M8: Risk Paper (Daily loss limit atau posisi terbuka pada simbol)
    # -------------------------------------------------------------
    m8_passed = True
    m8_detail = "Batas risiko harian dan posisi terbuka aman"
    if ctx.daily_loss_limit_reached:
        m8_passed = False
        m8_detail = "Batas kerugian harian paper trade (3%) tercapai — sistem jeda sampai esok"
    elif ctx.has_open_position_for_symbol:
        m8_passed = False
        m8_detail = f"Sudah ada posisi terbuka untuk simbol {ctx.symbol}"

    checks.append(
        MacroCheck(id="M8", name="Batas Risiko Paper", passed=m8_passed, detail=m8_detail)
    )

    # Consolidated output
    blocked_by = [c.id for c in checks if not c.passed]
    passed = len(blocked_by) == 0

    return MacroFilterResult(
        passed=passed,
        checks=checks,
        blocked_by=blocked_by,
    )
