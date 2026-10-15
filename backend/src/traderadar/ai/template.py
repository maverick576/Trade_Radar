"""Rule-based template provider for guaranteed offline and fallback commentary."""

from traderadar.ai.base import AIProvider
from traderadar.ai.schemas import (
    AIComment,
    AIInputPayload,
    MarketBriefNarrative,
    MarketBriefPayload,
    SymbolBriefNarrative,
)


class TemplateProvider(AIProvider):
    """Deterministic template generator that strictly adheres to schema and input numbers."""

    @property
    def name(self) -> str:
        return "template"

    @property
    def model_name(self) -> str:
        return "template-rule-engine-v1"

    async def generate_comment(self, payload: AIInputPayload) -> tuple[AIComment, int, int]:
        verdict = payload.verdict.upper()

        if "LONG" in verdict:
            bias = "bullish"
            keyakinan = "tinggi" if "STRONG" in verdict else "sedang"
        elif "SHORT" in verdict:
            bias = "bearish"
            keyakinan = "tinggi" if "STRONG" in verdict else "sedang"
        else:
            bias = "netral"
            keyakinan = "rendah"

        # 1. Alasan utama dari indikator searah
        target_state = "BULL" if bias == "bullish" else "BEAR"
        supporting_reasons: list[str] = []
        for ind in payload.indicators:
            if ind.get("state") == target_state:
                reason_txt = ind.get("reason", "").strip()
                if reason_txt and len(reason_txt) >= 3:
                    supporting_reasons.append(f"{ind.get('key', '').upper()}: {reason_txt}")

        if len(supporting_reasons) < 2:
            supporting_reasons.append(
                f"Skor konfluensi {payload.score:.1f} berada di zona {bias.upper()}."
            )
            supporting_reasons.append(
                f"Tercatat {payload.counts.get(target_state, 0)} indikator searah momentum."
            )
        alasan_utama = supporting_reasons[:4]

        # 2. Risiko dari indikator berlawanan
        opposing_state = "BEAR" if bias == "bullish" else "BULL"
        opposing_risks: list[str] = []
        for ind in payload.indicators:
            if ind.get("state") == opposing_state:
                reason_txt = ind.get("reason", "").strip()
                if reason_txt:
                    opposing_risks.append(f"Divergensi {ind.get('key', '').upper()}: {reason_txt}")

        macro_checks = payload.macro.get("checks", [])
        for chk in macro_checks:
            if not chk.get("passed", True):
                opposing_risks.append(f"Filter {chk.get('gate')}: {chk.get('detail')}")

        if not opposing_risks:
            opposing_risks = [
                "Volatilitas pasar dapat meningkat jelang penutupan sesi.",
                "Waspadai potensi false breakout pada level resistensi terdekat.",
            ]
        risiko = opposing_risks[:3]

        # 3. Kumpulkan level penting HANYA dari input data
        level_penting: list[float] = []
        if payload.plan:
            for k in ["entry", "sl", "tp1", "tp2"]:
                val = payload.plan.get(k)
                if val is not None and isinstance(val, (int, float)):
                    level_penting.append(float(val))

        if not level_penting:
            level_penting.append(payload.price)
            for ind in payload.indicators:
                vals = ind.get("values", {})
                for k in ["vwap", "supertrend", "middle_band", "ema21"]:
                    if k in vals and isinstance(vals[k], (int, float)):
                        level_penting.append(float(vals[k]))
                        break

        # Pastikan unik dan terurut
        level_penting = sorted(dict.fromkeys(level_penting))

        # 4. Ringkasan
        ringkasan = (
            f"Analisis M15 untuk {payload.symbol} menunjukkan bias {bias} "
            f"dengan skor konfluensi {payload.score:.1f}. "
            f"Tercatat {payload.counts.get('BULL', 0)} indikator Bullish, "
            f"{payload.counts.get('BEAR', 0)} Bearish, dan {payload.counts.get('NEUTRAL', 0)} "
            f"Netral. Konfirmasi tren sejalan dengan struktur momentum pasar, "
            f"namun tetap perhatikan potensi koreksi di sekitar level kunci."
        )

        inval_text = "Penembusan garis Supertrend atau swing terdekat berlawanan arah."
        if payload.plan and payload.plan.get("sl"):
            inval_text = (
                f"Penembusan harga candle close di bawah/atas level SL {payload.plan['sl']}."
            )

        ref_lvl = level_penting[0] if level_penting else payload.price
        skenario_bullish = (
            f"Bila buyer mempertahankan harga di atas {ref_lvl}, "
            f"target penguatan terbuka menuju resistance terdekat."
        )
        skenario_bearish = (
            f"Jika terjadi rejection dan harga tertekan di bawah {ref_lvl}, "
            f"potensi pelemahan lanjutan terbuka menuju level invalidasi."
        )

        comment = AIComment(
            ringkasan=ringkasan,
            bias=bias,
            keyakinan=keyakinan,
            setuju_dengan_engine=True,
            alasan_utama=alasan_utama,
            risiko=risiko,
            skenario_bullish=skenario_bullish,
            skenario_bearish=skenario_bearish,
            level_penting=level_penting,
            invalidasi=inval_text,
            saran_manajemen=(
                "Gunakan risiko maksimal 1% per posisi, amankan 50% di TP1 dan geser SL ke BE."
            ),
        )
        return comment, 0, 0

    async def generate_brief(
        self, payload: MarketBriefPayload
    ) -> tuple[MarketBriefNarrative, int, int]:
        symbols_narrative: dict[str, SymbolBriefNarrative] = {}

        bull_count = 0
        bear_count = 0

        for sym, data in payload.symbols.items():
            b_h4 = data.bias_h4.lower()
            if "bull" in b_h4 or data.score_m15 > 30:
                sym_bias = "bullish"
                bull_count += 1
            elif "bear" in b_h4 or data.score_m15 < -30:
                sym_bias = "bearish"
                bear_count += 1
            else:
                sym_bias = "netral"

            levels: list[float] = [data.daily_low, data.last_price, data.daily_high]
            if data.vwap_yesterday:
                levels.append(data.vwap_yesterday)
            levels = sorted(dict.fromkeys(levels))

            narasi_sym = (
                f"{sym} bergerak dengan bias {sym_bias}. Harga terakhir {data.last_price} "
                f"dengan rentang harian {data.daily_low} - {data.daily_high}. "
                f"Skor M15 mencatatkan {data.score_m15:.1f} ({data.verdict_m15}). "
                f"Kondisi bias HTF H4 ({data.bias_h4}) dan D1 ({data.bias_d1}) jadi acuan tren."
            )

            symbols_narrative[sym] = SymbolBriefNarrative(
                symbol=sym,
                bias=sym_bias,
                ringkasan=narasi_sym,
                level_kunci=levels,
                skenario=f"Pantau reaksi harga di rentang {data.daily_low} - {data.daily_high}.",
                fokus_perhatian="Konfirmasi breakout pada timeframe H1 dan kestabilan volume.",
            )

        if bull_count > bear_count:
            sentimen = "Risk-On (Kecenderungan Penguatan)"
        elif bear_count > bull_count:
            sentimen = "Risk-Off (Kecenderungan Tekanan Jual)"
        else:
            sentimen = "Konsolidasi / Netral"

        hdr = f"Market Brief {payload.kind.capitalize()} {payload.generated_at}"
        ringkasan_umum = (
            f"{hdr}: Pasar dalam {sentimen}. "
            f"Dari {len(payload.symbols)} instrumen dipantau, {bull_count} bullish, "
            f"{bear_count} bearish, dan sisanya netral/konsolidasi. "
            f"Tercatat {len(payload.high_impact_news_today)} rilis berita high-impact hari ini."
        )

        brief = MarketBriefNarrative(
            ringkasan_umum=ringkasan_umum,
            market_sentiment=sentimen,
            symbols=symbols_narrative,
        )
        return brief, 0, 0
