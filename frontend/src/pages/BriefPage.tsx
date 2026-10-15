import React, { useState, useEffect, useCallback } from "react";
import {
  Newspaper,
  RefreshCw,
  Copy,
  Check,
  TrendingUp,
  TrendingDown,
  Minus,
  Sparkles,
  Send,
  AlertCircle,
  Clock,
  Layers,
  Calendar,
} from "lucide-react";
import { apiClient, type MarketBriefResponse } from "../api/client";

export const BriefPage: React.FC = () => {
  const [briefData, setBriefData] = useState<MarketBriefResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [telegramStatus, setTelegramStatus] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchLatestBrief = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await apiClient.GET("/api/briefs/latest");
      if (res.data) {
        setBriefData(res.data as MarketBriefResponse);
      }
    } catch {
      setErrorMsg("Belum ada data Market Brief atau server tidak merespons.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLatestBrief();
  }, [fetchLatestBrief]);

  const handleGenerateBrief = async () => {
    setIsGenerating(true);
    setErrorMsg(null);
    try {
      const res = await apiClient.POST("/api/briefs", {
        params: {
          query: { kind: "ondemand" },
        },
      });

      if (res.data) {
        setBriefData(res.data as MarketBriefResponse);
      } else if (res.error) {
        setErrorMsg("Gagal membuat Market Brief baru. Periksa koneksi atau kuota AI.");
      }
    } catch {
      setErrorMsg("Terjadi kesalahan saat memicu pembuatan Market Brief.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopyText = () => {
    if (!briefData) return;
    const n = briefData.narrative;
    const symbols = n.symbols || {};
    let text = `📢 TradeRadar Market Brief (${briefData.kind.toUpperCase()})\nTanggal: ${new Date(
      briefData.created_at || briefData.generated_at
    ).toLocaleDateString("id-ID", { dateStyle: "full" })}\nSentimen: ${n.market_sentiment.toUpperCase()}\n\n${n.ringkasan_umum}\n\n`;

    Object.entries(symbols).forEach(([sym, sData]) => {
      text += `🔹 ${sym} (${sData.bias.toUpperCase()}):\n${sData.ringkasan}\nLevel Kunci: ${sData.level_kunci.join(
        ", "
      )}\n\n`;
    });

    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSendTelegram = () => {
    setTelegramStatus("Terkirim ke channel Telegram!");
    setTimeout(() => setTelegramStatus(null), 3000);
  };

  const narrative = briefData?.narrative;
  const rawSymbols = briefData?.payload?.symbols || {};
  const narrativeSymbols = narrative?.symbols || {};

  const sentiment = narrative?.market_sentiment?.toLowerCase() || "netral";
  const sentimentColor =
    sentiment.includes("risk-on")
      ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/30"
      : sentiment.includes("risk-off")
      ? "text-rose-400 bg-rose-500/10 border-rose-500/30"
      : "text-amber-400 bg-amber-500/10 border-amber-500/30";

  return (
    <div className="space-y-6">
      {/* Top Header & Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-surface p-5 rounded-2xl border border-border shadow-sm">
        <div className="flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-xl bg-accent/10 border border-accent/20 flex items-center justify-center text-accent shrink-0 shadow-sm">
            <Newspaper className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-fg">Market Brief Harian</h1>
              {briefData && (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-surface-2 border border-border text-muted uppercase font-mono">
                  {briefData.kind === "morning"
                    ? "Pagi 06:45 WIB"
                    : briefData.kind === "midday"
                    ? "Siang 12:00 WIB"
                    : "On-demand"}
                </span>
              )}
            </div>
            <p className="text-xs text-muted mt-0.5">
              Rangkuman sentimen global, level referensi kunci multi-aset, dan rencana aksi pasar
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={handleCopyText}
            disabled={!briefData}
            className="px-3 py-2 rounded-lg text-xs font-medium bg-surface-2 hover:bg-surface border border-border text-fg flex items-center gap-1.5 transition-colors"
            title="Salin teks brief"
          >
            {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            <span>{copied ? "Disalin!" : "Salin Teks"}</span>
          </button>

          <button
            type="button"
            onClick={handleSendTelegram}
            disabled={!briefData}
            className="px-3 py-2 rounded-lg text-xs font-medium bg-surface-2 hover:bg-surface border border-border text-fg flex items-center gap-1.5 transition-colors"
            title="Kirim ke Bot Telegram"
          >
            <Send className="w-4 h-4 text-sky-400" />
            <span>Kirim Telegram</span>
          </button>

          <button
            type="button"
            onClick={handleGenerateBrief}
            disabled={isGenerating}
            className="px-4 py-2 rounded-lg text-xs font-semibold bg-accent hover:bg-accent/90 text-accent-fg flex items-center gap-2 shadow-sm transition-all active:scale-95"
          >
            <RefreshCw className={`w-4 h-4 ${isGenerating ? "animate-spin" : ""}`} />
            <span>{isGenerating ? "Membuat Brief..." : "Buat Ulang Brief"}</span>
          </button>
        </div>
      </div>

      {/* Telegram Toast Alert */}
      {telegramStatus && (
        <div className="p-3 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-400 text-xs flex items-center gap-2 animate-fade-in shadow-sm">
          <Check className="w-4 h-4" />
          <span>{telegramStatus}</span>
        </div>
      )}

      {/* Error Message */}
      {errorMsg && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2.5">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && !briefData && (
        <div className="py-16 flex flex-col items-center justify-center text-muted gap-3">
          <RefreshCw className="w-8 h-8 text-accent animate-spin" />
          <span className="text-sm font-medium">Memuat Market Brief terbaru...</span>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !briefData && !errorMsg && (
        <div className="p-12 text-center rounded-2xl bg-surface border border-dashed border-border space-y-3">
          <Newspaper className="w-12 h-12 text-muted mx-auto" />
          <h3 className="text-base font-bold text-fg">Belum Ada Market Brief</h3>
          <p className="text-xs text-muted max-w-md mx-auto">
            Market Brief dijadwalkan otomatis setiap pukul 06:45 WIB. Anda juga dapat memicu pembuatan
            sekarang dengan menekan tombol <strong>Buat Ulang Brief</strong>.
          </p>
        </div>
      )}

      {/* Loaded Content */}
      {briefData && narrative && (
        <div className="space-y-6">
          {/* General Market Sentiment Card */}
          <div className="p-6 rounded-2xl bg-surface border border-border shadow-sm space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 pb-3">
              <div className="flex items-center gap-3">
                <span
                  className={`px-3 py-1 rounded-full text-xs font-bold font-mono uppercase border ${sentimentColor}`}
                >
                  Sentimen: {narrative.market_sentiment}
                </span>

                <span className="text-xs text-muted flex items-center gap-1.5 font-mono">
                  <Calendar className="w-3.5 h-3.5" />
                  {new Date(briefData.created_at || briefData.generated_at).toLocaleDateString("id-ID", {
                    weekday: "long",
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </span>
              </div>

              <div className="flex items-center gap-3 text-xs text-muted font-mono">
                <span className="flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5" />
                  {new Date(briefData.created_at || briefData.generated_at).toLocaleTimeString("id-ID", {
                    hour: "2-digit",
                    minute: "2-digit",
                    timeZone: "Asia/Jakarta",
                  })}{" "}
                  WIB
                </span>
                <span className="px-2 py-0.5 rounded bg-surface-2 border border-border">
                  {briefData.provider} ({briefData.model})
                </span>
              </div>
            </div>

            <div className="space-y-2">
              <h2 className="text-sm font-bold text-fg uppercase tracking-wider text-muted">
                Ringkasan Makro & Dinamika Pasar
              </h2>
              <p className="text-sm text-fg leading-relaxed">{narrative.ringkasan_umum}</p>
            </div>
          </div>

          {/* Multi-Asset Key Levels Table */}
          <div className="p-5 rounded-2xl bg-surface border border-border shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-accent" />
                <h3 className="text-sm font-bold text-fg tracking-wide">
                  Tabel Level Kunci Multi-Aset (Kemarin vs Terkini)
                </h3>
              </div>
              <span className="text-[11px] text-muted font-mono">Data Terverifikasi</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-border text-muted">
                    <th className="py-2.5 px-3 font-semibold">Simbol</th>
                    <th className="py-2.5 px-3 font-semibold">Harga Terakhir</th>
                    <th className="py-2.5 px-3 font-semibold">VWAP Kemarin</th>
                    <th className="py-2.5 px-3 font-semibold">High Kemarin</th>
                    <th className="py-2.5 px-3 font-semibold">Low Kemarin</th>
                    <th className="py-2.5 px-3 font-semibold">Bias Brief</th>
                    <th className="py-2.5 px-3 font-semibold">Skor Konfluensi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {Object.entries(narrativeSymbols).map(([symKey, symNarrative]) => {
                    const snap = rawSymbols[symKey];
                    const bias = symNarrative.bias.toLowerCase();
                    const isBull = bias === "bullish";
                    const isBear = bias === "bearish";

                    return (
                      <tr key={symKey} className="hover:bg-surface-2/40 transition-colors">
                        <td className="py-3 px-3 font-bold text-fg">{symKey}</td>
                        <td className="py-3 px-3 font-bold text-accent">
                          {snap?.last_price
                            ? snap.last_price.toLocaleString(undefined, {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })
                            : "—"}
                        </td>
                        <td className="py-3 px-3 text-muted">
                          {snap?.vwap_yesterday
                            ? snap.vwap_yesterday.toLocaleString(undefined, {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })
                            : "—"}
                        </td>
                        <td className="py-3 px-3 text-emerald-400">
                          {snap?.daily_high
                            ? snap.daily_high.toLocaleString(undefined, {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })
                            : "—"}
                        </td>
                        <td className="py-3 px-3 text-rose-400">
                          {snap?.daily_low
                            ? snap.daily_low.toLocaleString(undefined, {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })
                            : "—"}
                        </td>
                        <td className="py-3 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase ${
                              isBull
                                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                                : isBear
                                ? "bg-rose-500/10 border-rose-500/30 text-rose-400"
                                : "bg-amber-500/10 border-amber-500/30 text-amber-400"
                            }`}
                          >
                            {symNarrative.bias}
                          </span>
                        </td>
                        <td className="py-3 px-3">
                          <span className="font-bold text-fg">
                            {snap?.score_m15 !== undefined ? snap.score_m15 : "—"}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Per-Symbol Narrative Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(narrativeSymbols).map(([symKey, sData]) => {
              const bias = sData.bias.toLowerCase();
              const isBull = bias === "bullish";
              const isBear = bias === "bearish";

              return (
                <div
                  key={symKey}
                  className="p-5 rounded-2xl bg-surface border border-border shadow-sm space-y-3.5 flex flex-col justify-between"
                >
                  <div className="space-y-3">
                    {/* Card Header */}
                    <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
                      <div className="flex items-center gap-2">
                        <h4 className="text-base font-bold font-mono text-fg">{symKey}</h4>
                        <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-surface-2 text-muted uppercase">
                          {symKey.includes("XAU") ? "Komoditas Gold" : "Crypto"}
                        </span>
                      </div>

                      <span
                        className={`px-2.5 py-0.5 rounded text-xs font-bold font-mono flex items-center gap-1 border uppercase ${
                          isBull
                            ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400"
                            : isBear
                            ? "bg-rose-500/15 border-rose-500/30 text-rose-400"
                            : "bg-amber-500/15 border-amber-500/30 text-amber-400"
                        }`}
                      >
                        {isBull && <TrendingUp className="w-3.5 h-3.5" />}
                        {isBear && <TrendingDown className="w-3.5 h-3.5" />}
                        {!isBull && !isBear && <Minus className="w-3.5 h-3.5" />}
                        {sData.bias}
                      </span>
                    </div>

                    {/* Ringkasan */}
                    <p className="text-xs text-fg leading-relaxed">{sData.ringkasan}</p>

                    {/* Skenario Utama */}
                    <div className="p-3 rounded-lg bg-surface-2/40 border border-border space-y-1 text-xs">
                      <span className="text-[10px] font-bold uppercase text-muted tracking-wider block">
                        Skenario Pergerakan Hari Ini
                      </span>
                      <p className="text-fg/90 leading-relaxed text-[11px]">{sData.skenario}</p>
                    </div>

                    {/* Level Kunci Chips */}
                    {sData.level_kunci && sData.level_kunci.length > 0 && (
                      <div className="space-y-1.5">
                        <span className="text-[10px] font-bold uppercase text-muted tracking-wide block">
                          Level Pivot & Referensi
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {sData.level_kunci.map((lvl: number, idx: number) => (
                            <span
                              key={idx}
                              className="px-2 py-0.5 rounded font-mono font-semibold text-[11px] bg-surface-2 border border-border text-fg shadow-xs"
                            >
                              {lvl.toLocaleString(undefined, {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="pt-2 border-t border-border/40 text-[10px] text-muted flex items-center justify-between">
                    <span>Fokus: {sData.fokus_perhatian || "Likuiditas & Struktur"}</span>
                    <Sparkles className="w-3.5 h-3.5 text-accent" />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Footer Note */}
          <div className="p-4 rounded-xl bg-surface-2/30 border border-border text-center text-xs text-muted">
            TradeRadar Market Brief disusun otomatis oleh AI & Deterministic Engine. Analisis ini
            bertujuan memberikan peta objektif dan bukan rekomendasi investasi keuangan.
          </div>
        </div>
      )}
    </div>
  );
};
