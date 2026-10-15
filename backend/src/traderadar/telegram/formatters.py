"""Telegram message formatters in Indonesian Markdown.

Formats trade tickets, confluence analyses, market briefs, paper trade positions,
winrate metrics, calendar events, and operational alerts.
"""

from typing import Any
from zoneinfo import ZoneInfo

from traderadar.core.models import PaperTradeRecord, TicketRecord
from traderadar.core.time import to_wib
from traderadar.engine.ticket import TradeTicket

WIB = ZoneInfo("Asia/Jakarta")

DISCLAIMER_TEXT = (
    "⚠️ *TradeRadar adalah alat bantu analisis, bukan nasihat keuangan.*\n"
    "_Harga sumber data dapat berbeda dari broker Anda — selalu cek ulang sebelum eksekusi. "
    "Winrate historis tidak menjamin hasil di masa depan._"
)


def format_start_message(chat_id: int, is_allowed: bool) -> str:
    """Format welcome message with chat ID, auth status, and disclaimer."""
    status_str = (
        "✅ *Terdaftar & Terverifikasi*"
        if is_allowed
        else "⚠️ *Belum Terdaftar di Whitelist*"
    )
    instruction = (
        "Gunakan perintah /help untuk melihat daftar menu analisis dan eksekusi."
        if is_allowed
        else (
            "Salin *Chat ID* di atas, tambahkan ke `TELEGRAM_ALLOWED_CHAT_IDS` di file `.env`, "
            "lalu restart aplikasi."
        )
    )

    return (
        f"👋 *Selamat Datang di TradeRadar Bot*\n\n"
        f"🆔 *Chat ID Anda:* `{chat_id}`\n"
        f"🔐 *Status Akses:* {status_str}\n\n"
        f"{instruction}\n\n"
        f"{DISCLAIMER_TEXT}"
    )


def format_help_message() -> str:
    """Format list of available commands in Indonesian."""
    return (
        "📖 *Daftar Perintah TradeRadar:*\n\n"
        "📊 *Analisis & Pasar:*\n"
        "• `/analisa <SIMBOL> [TF]` — Analisis konfluensi + chart PNG + ulasan AI\n"
        "  _Contoh:_ `/analisa XAUUSD` atau `/analisa BTCUSDT H1`\n"
        "• `/brief` — Market Brief terbaru (edisi Pagi/Siang)\n"
        "• `/kalender` — Kalender berita ekonomi High-Impact 48 jam\n\n"
        "🎯 *Ticket & Eksekusi:*\n"
        "• `/ticket` — Lihat daftar Trade Ticket aktif yang siap dieksekusi\n"
        "• `/kalibrasi <SIMBOL> <HARGA>` — Set offset harga broker Anda (berlaku 4 jam)\n"
        "  _Contoh:_ `/kalibrasi XAUUSD 2652.3`\n"
        "• `/eksekusi <ID> <HARGA> <LOT>` — Catat eksekusi nyata ke Jurnal Real\n"
        "  _Contoh:_ `/eksekusi 12 2651.5 0.06`\n"
        "• `/tutup <ID> <HARGA>` — Tutup posisi riil & hitung laba/rugi\n"
        "  _Contoh:_ `/tutup 12 2665.5`\n\n"
        "📈 *Jurnal & Kinerja:*\n"
        "• `/posisi` — Daftar posisi Paper Trading yang sedang berjalan\n"
        "• `/winrate [7d|30d|all] [paper|real]` — Statistik performa trading\n"
        "  _Contoh:_ `/winrate 7d real` atau `/winrate all paper`\n\n"
        "⚙️ *Pengaturan Notifikasi:*\n"
        "• `/pause` — Jeda sementara pengiriman notifikasi otomatis\n"
        "• `/resume` — Aktifkan kembali notifikasi otomatis\n"
        "• `/help` — Tampilkan bantuan ini"
    )


def format_ticket_message(
    ticket: TradeTicket | TicketRecord,
    ai_comment: str | None = None,
    confirmed_by_b: bool = False,
) -> str:
    """Format professional trade ticket with key levels, sizing, and reasons."""
    t_id = getattr(ticket, "id", None) or "BARU"
    is_long = str(ticket.side).upper() in ("LONG", "BUY")
    side_emoji = "🟢" if is_long else "🔴"
    action_word = "BUY" if is_long else "SELL"

    lines: list[str] = [
        f"{side_emoji} *TRADE TICKET #{t_id} · {action_word} {ticket.symbol}*",
    ]

    if confirmed_by_b:
        lines.append("✅ *Dikonfirmasi Triple-EMA (Strategi B)*")

    lines.append(f"📋 *Strategi:* {ticket.strategy} · *Skor:* {ticket.score:.1f}/100")
    lines.append(
        f"🎯 *Zona Entry:* `{ticket.entry_low:.2f}` – `{ticket.entry_high:.2f}`\n"
        f"   (Target: `{ticket.entry:.2f}`)"
    )
    lines.append(
        f"🛑 *Stop Loss:* `{ticket.sl:.2f}` "
        f"(-{ticket.sl_points:.2f} pts · {ticket.sl_atr_mult:.1f}×ATR)"
    )
    lines.append(
        f"🎯 *TP1 (50% & SL→BE):* `{ticket.tp1:.2f}` (+{ticket.tp1_points:.2f} pts · 1.0R)"
    )
    lines.append(f"🏆 *TP2 (50%):* `{ticket.tp2:.2f}` (+{ticket.tp2_points:.2f} pts · 2.0R)")

    if ticket.suggested_lot is not None:
        risk_usd = ticket.actual_risk_usd or 0.0
        risk_pct = ticket.actual_risk_pct or 0.0
        lines.append(
            f"⚖️ *Rekomendasi Lot:* `{ticket.suggested_lot:.2f} lot` "
            f"(Risiko: ${risk_usd:.2f} · {risk_pct:.2f}%)"
        )

    if ticket.broker_offset is not None and ticket.broker_offset != 0:
        lines.append(
            f"ℹ️ _Disesuaikan untuk broker ({ticket.broker_offset:+.2f} poin offset terpasang)_"
        )

    if ticket.min_lot_warning:
        lines.append("⚠️ _Peringatan: Risiko lot minimum broker melebihi batas toleransi!_")

    lines.append(f"⛔ *Invalidasi:* {ticket.invalidation}")

    if ticket.reasons:
        reasons_text = "\n".join(f"  • {r}" for r in ticket.reasons[:3])
        lines.append(f"💡 *Alasan Konfluensi:*\n{reasons_text}")

    if ticket.risks:
        risks_text = "\n".join(f"  • {r}" for r in ticket.risks[:2])
        lines.append(f"⚡ *Risiko Diwaspadai:*\n{risks_text}")

    if ai_comment:
        clean_ai = ai_comment.strip()
        if len(clean_ai) > 280:
            clean_ai = clean_ai[:277] + "..."
        lines.append(f"🤖 *Ulasan AI:* {clean_ai}")

    exp_wib = to_wib(ticket.valid_until).strftime("%H:%M")
    lines.append(f"\n⏳ _Berlaku hingga {exp_wib} WIB (maks 3 bar M15)_")

    return "\n".join(lines)


def format_ticket_detail_message(ticket: TicketRecord) -> str:
    """Format expanded detail breakdown for inline [Detail] button."""
    is_long = str(ticket.side).upper() in ("LONG", "BUY")
    side_emoji = "🟢" if is_long else "🔴"
    created_wib = to_wib(ticket.created_at).strftime("%d-%m-%Y %H:%M")
    exp_wib = to_wib(ticket.valid_until).strftime("%H:%M")

    reasons = "\n".join(f"• {r}" for r in (ticket.reasons or []))
    risks = "\n".join(f"• {r}" for r in (ticket.risks or []))

    return (
        f"📊 *DETAIL LENGKAP TICKET #{ticket.id}*\n"
        f"Instrumen: *{ticket.symbol}* ({ticket.side} {side_emoji})\n"
        f"Waktu Dibuat: {created_wib} WIB\n"
        f"Batas Waktu: {exp_wib} WIB\n"
        f"Skor Konfluensi: {ticket.score:.1f}/100\n\n"
        f"📐 *Parameter Teknikal:*\n"
        f"• ATR14: {ticket.atr:.2f}\n"
        f"• SL Distance: {ticket.sl_points:.2f} pts ({ticket.sl_atr_mult:.1f}×ATR)\n"
        f"• TP1 Distance: {ticket.tp1_points:.2f} pts (1.0R)\n"
        f"• TP2 Distance: {ticket.tp2_points:.2f} pts (2.0R)\n"
        f"• Offset Broker: {ticket.broker_offset or 0.0:+.2f} pts\n\n"
        f"💡 *Faktor Pendukung:*\n{reasons or '• Tidak ada catatan khusus'}\n\n"
        f"⚠️ *Faktor Risiko:*\n{risks or '• Tidak ada catatan khusus'}\n\n"
        f"⛔ *Kondisi Pembatalan:* {ticket.invalidation}"
    )


def format_analysis_message(
    analysis: dict[str, Any],
    symbol: str,
    tf: str,
    ai_comment: dict[str, Any] | None = None,
) -> str:
    """Format on-demand confluence analysis result with AI review."""
    score = float(analysis.get("score", 0.0))
    verdict = str(analysis.get("verdict", "NEUTRAL"))
    counts = analysis.get("counts", {})
    bull_count = counts.get("bull", 0)
    bear_count = counts.get("bear", 0)
    neutral_count = counts.get("neutral", 0)

    verdict_emoji = {
        "STRONG_LONG": "🚀 *STRONG BUY*",
        "LONG": "📈 *BUY*",
        "NEUTRAL": "⚖️ *NETRAL*",
        "SHORT": "📉 *SELL*",
        "STRONG_SHORT": "🔻 *STRONG SELL*",
    }.get(verdict, verdict)

    lines: list[str] = [
        f"📊 *HASIL ANALISIS · {symbol.upper()} [{tf.upper()}]*",
        f"Keputusan: {verdict_emoji}",
        f"Skor Konfluensi: *{score:.1f}/100*",
        f"Distribusi: {bull_count} Bullish · {bear_count} Bearish · {neutral_count} Netral\n",
    ]

    # Indicator highlights
    indicators = analysis.get("indicators", [])
    if indicators:
        lines.append("🔍 *Sorotan Indikator:*")
        for ind in indicators[:5]:
            state = ind.get("state", "NEUTRAL")
            icon = "🟢" if state == "BULL" else ("🔴" if state == "BEAR" else "⚪")
            lines.append(f"{icon} *{ind.get('name', ind.get('key'))}:* {ind.get('reason', '')}")
        lines.append("")

    # Macro filter summary
    macro = analysis.get("macro", {})
    macro_passed = macro.get("passed", True)
    if not macro_passed:
        blocked = macro.get("blocked_by", [])
        lines.append(f"🛡️ *Filter Makro:* ⚠️ Terhalang ({', '.join(blocked)})")
    else:
        lines.append("🛡️ *Filter Makro:* ✅ Semua kondisi aman")

    # AI commentary if present
    if ai_comment:
        lines.append("\n🤖 *Tanggapan AI:*")
        bias = str(ai_comment.get("bias", "NETRAL")).upper()
        bias_icon = "🟢" if bias == "BULLISH" else ("🔴" if bias == "BEARISH" else "⚪")
        confidence = ai_comment.get("keyakinan", "Sedang")
        lines.append(f"Bias: {bias_icon} *{bias}* (Keyakinan: {confidence})")
        summary = ai_comment.get("ringkasan", "")
        if summary:
            lines.append(f"_{summary}_")

    return "\n".join(lines)


def format_brief_message(brief: dict[str, Any], kind: str = "morning") -> str:
    """Format daily morning or midday market brief."""
    title_kind = "Pagi" if kind == "morning" else ("Siang" if kind == "midday" else "Pasar")
    payload = brief.get("payload", {})
    narrative = brief.get("narrative", {})

    sentiment = payload.get("macro_sentiment", "Netral")
    sent_emoji = "🟢" if sentiment == "Risk-on" else ("🔴" if sentiment == "Risk-off" else "⚪")

    lines: list[str] = [
        f"🌅 *MARKET BRIEF {title_kind.upper()}*",
        f"Sentimen Global: {sent_emoji} *{sentiment}*\n",
    ]

    overview = narrative.get("ringkasan_umum", "")
    if overview:
        lines.append(f"📝 *Ringkasan Eksekutif:*\n{overview}\n")

    # Multi-asset highlights
    symbols_data = payload.get("symbols", {})
    if symbols_data:
        lines.append("📌 *Level Kunci Multi-Aset:*")
        for sym, d in symbols_data.items():
            price = d.get("current_price", 0.0)
            vwap = d.get("vwap_yesterday", 0.0)
            score = d.get("score", 0.0)
            lines.append(f"• *{sym}:* Harga `{price:.2f}` | VWAP `{vwap:.2f}` | Skor `{score:.0f}`")
        lines.append("")

    # Specific symbol scenario
    narrative_syms = narrative.get("simbol", {})
    if narrative_syms:
        lines.append("🧭 *Skenario Utama Hari Ini:*")
        for sym, n in narrative_syms.items():
            bias = n.get("bias", "Netral")
            skenario = n.get("skenario", "")
            lines.append(f"• *{sym} ({bias}):* {skenario}")

    return "\n".join(lines)


def format_paper_positions(positions: list[PaperTradeRecord]) -> str:
    """Format active open paper trading positions."""
    if not positions:
        return "ℹ️ *Tidak ada posisi Paper Trading yang sedang terbuka.*"

    lines: list[str] = [f"📋 *POSISI PAPER TRADING TERBUKA ({len(positions)}):*\n"]
    for p in positions:
        is_long = str(p.side).upper() in ("LONG", "BUY")
        side_emoji = "🟢" if is_long else "🔴"
        entry_wib = to_wib(p.entry_time).strftime("%H:%M")
        tp1_status = "✅ TP1 tercapai (SL di BE)" if p.tp1_hit else "⏳ Menuju TP1"

        lines.append(
            f"{side_emoji} *{p.symbol} · {p.side}*\n"
            f"• Entry: `{p.entry_price:.2f}` (Jam {entry_wib} WIB)\n"
            f"• SL: `{p.sl:.2f}` | TP1: `{p.tp1:.2f}` | TP2: `{p.tp2:.2f}`\n"
            f"• Durasi: {p.bars_held} bar M15 ({p.bars_held * 15} mnt)\n"
            f"• Status: _{tp1_status}_\n"
        )
    return "\n".join(lines)


def format_winrate_stats(stats: dict[str, Any], book: str = "paper", period: str = "all") -> str:
    """Format winrate and journal metrics."""
    book_title = "Paper Trading" if book.lower() == "paper" else "Eksekusi Nyata (Real)"
    total = stats.get("total_closed_trades", 0)
    winrate = stats.get("winrate_pct", 0.0)
    expectancy = stats.get("expectancy_r", 0.0)
    pnl_usd = stats.get("realized_pnl_usd", 0.0)
    profit_factor = stats.get("profit_factor", 0.0)

    pnl_icon = "🟢 +" if pnl_usd >= 0 else "🔴 -"
    abs_pnl = abs(pnl_usd)

    return (
        f"📈 *STATISTIK JURNAL · {book_title.upper()}*\n"
        f"Periode: *{period.upper()}*\n\n"
        f"• Total Trade Selesai: *{total}*\n"
        f"• Winrate: *{winrate:.1f}%*\n"
        f"• Expectancy: *{expectancy:+.2f} R*\n"
        f"• Profit Factor: *{profit_factor:.2f}*\n"
        f"• Realized PnL: {pnl_icon}*${abs_pnl:.2f}*\n\n"
        f"_{stats.get('note', 'Dihitung dari transaksi yang telah selesai di database.')}_"
    )


def format_calendar_news(events: list[dict[str, Any]]) -> str:
    """Format high-impact economic calendar events for the next 48 hours."""
    if not events:
        return "📅 *Kalender Berita:* Tidak ada agenda berita High-Impact dalam 48 jam ke depan."

    lines: list[str] = ["📅 *AGENDA BERITA HIGH-IMPACT (48 JAM KE DEPAN):*\n"]
    for ev in events:
        time_str = ev.get("time_wib", "")
        currency = ev.get("currency", "USD")
        title = ev.get("title", "News Event")
        forecast = ev.get("forecast", "-")
        previous = ev.get("previous", "-")

        lines.append(
            f"🔴 *[{currency}] {title}*\n"
            f"  ⏰ Waktu: {time_str} WIB\n"
            f"  📊 Forecast: {forecast} | Previous: {previous}\n"
        )
    lines.append("⚠️ _Blackout trading berlaku ±30 menit sebelum dan sesudah berita High USD._")
    return "\n".join(lines)


def format_paper_exit_notification(
    trade: dict[str, Any] | PaperTradeRecord,
    reason: str,
) -> str:
    """Format notification when a paper trading position exits."""
    sym = trade.get("symbol", "") if isinstance(trade, dict) else trade.symbol
    side = trade.get("side", "") if isinstance(trade, dict) else trade.side
    pnl_usd_val = trade.get("pnl_usd", 0.0) if isinstance(trade, dict) else trade.pnl_usd
    pnl_r_val = trade.get("pnl_r", 0.0) if isinstance(trade, dict) else trade.pnl_r
    pnl_usd = float(pnl_usd_val or 0.0)
    pnl_r = float(pnl_r_val or 0.0)

    pnl_sign = "+" if pnl_usd >= 0 else "-"
    abs_usd = abs(pnl_usd)

    if reason in ("TP1", "TP1_HIT"):
        return (
            f"🎯 *TARGET TP1 TERCAPAI · {side} {sym}*\n"
            f"50% posisi otomatis ditutup, Stop Loss telah digeser ke titik Breakeven (BE)!"
        )
    elif reason in ("TP2", "TP2_HIT"):
        return (
            f"🏆 *TARGET TP2 TERCAPAI (SELESAI) · {side} {sym}*\n"
            f"Hasil Transaksi: *{pnl_sign}${abs_usd:.2f}* (*{pnl_r:+.2f} R*)\n"
            f"Semua posisi telah ditutup dengan sukses."
        )
    elif reason in ("SL", "SL_HIT"):
        return (
            f"🛑 *STOP LOSS TERKENAI · {side} {sym}*\n"
            f"Hasil Transaksi: *{pnl_sign}${abs_usd:.2f}* (*{pnl_r:+.2f} R*)\n"
            f"Disiplin manajemen risiko diterapkan."
        )
    elif reason in ("TIME_STOP", "time_stop"):
        return (
            f"⏱ *TIME STOP TERPENUHI · {side} {sym}*\n"
            f"Posisi ditutup setelah 32 bar (8 jam).\n"
            f"Hasil: *{pnl_sign}${abs_usd:.2f}* (*{pnl_r:+.2f} R*)."
        )
    elif reason in ("OPPOSITE", "opposite"):
        return (
            f"🔄 *OPPOSITE EXIT · {side} {sym}*\n"
            f"Posisi ditutup karena terdeteksi sinyal berlawanan arah.\n"
            f"Hasil: *{pnl_sign}${abs_usd:.2f}* (*{pnl_r:+.2f} R*)."
        )
    else:
        return (
            f"🏁 *POSISI DITUTUP · {side} {sym}*\n"
            f"Alasan: {reason} | PnL: *{pnl_sign}${abs_usd:.2f}* (*{pnl_r:+.2f} R*)"
        )


def format_ticket_expired_notification(ticket_id: int, symbol: str, reason: str) -> str:
    """Format notification when an active trade ticket expires."""
    reason_id = {
        "EXPIRED_TIME": "Batas waktu 3 bar (45 mnt) terlampaui",
        "CHASE_LIMIT": "Harga melesat > 0.5×ATR sebelum sempat terisi",
        "SL_HIT_BEFORE_ENTRY": "Harga menyentuh level SL sebelum masuk zona entry",
    }.get(reason, reason)

    return (
        f"⌛ *TRADE TICKET #{ticket_id} KEDALUWARSA · {symbol}*\n"
        f"Alasan Pembatalan: _{reason_id}_\n"
        f"Ticket tidak lagi valid untuk dieksekusi."
    )


def format_system_status_notification(service: str, status: str, details: str = "") -> str:
    """Format alert when a service health status changes."""
    status_icon = "🟢" if status.lower() == "healthy" else "⚠️"
    msg = f"{status_icon} *STATUS SISTEM · {service.upper()}*\nKondisi: *{status.upper()}*"
    if details:
        msg += f"\nKeterangan: {details}"
    return msg


def format_daily_recap_message(
    date_str: str,
    paper_trades: list[Any],
    real_executions: list[Any],
) -> str:
    """Format 22:00 WIB daily trading recap."""
    paper_closed = len(paper_trades)
    paper_wins = sum(1 for t in paper_trades if (getattr(t, "pnl_r", 0.0) or 0.0) > 0)
    paper_wr = (paper_wins / paper_closed * 100.0) if paper_closed else 0.0
    paper_pnl = sum((getattr(t, "pnl_usd", 0.0) or 0.0) for t in paper_trades)

    real_closed = len(real_executions)
    real_wins = sum(1 for r in real_executions if (getattr(r, "pnl_r", 0.0) or 0.0) > 0)
    real_wr = (real_wins / real_closed * 100.0) if real_closed else 0.0
    real_pnl = sum((getattr(r, "pnl_usd", 0.0) or 0.0) for r in real_executions)

    return (
        f"🌙 *REKAP HARIAN TRADERADAR (22:00 WIB)*\n"
        f"Tanggal: {date_str}\n\n"
        f"📊 *Paper Trading Hari Ini:*\n"
        f"• Selesai: *{paper_closed} trade* (Menang: {paper_wins})\n"
        f"• Winrate: *{paper_wr:.1f}%*\n"
        f"• Total PnL: *{'+' if paper_pnl >= 0 else ''}${paper_pnl:.2f}*\n\n"
        f"💼 *Jurnal Eksekusi Nyata:*\n"
        f"• Selesai: *{real_closed} trade* (Menang: {real_wins})\n"
        f"• Winrate: *{real_wr:.1f}%*\n"
        f"• Total PnL: *{'+' if real_pnl >= 0 else ''}${real_pnl:.2f}*\n\n"
        f"_Terima kasih dan selamat beristirahat._"
    )
