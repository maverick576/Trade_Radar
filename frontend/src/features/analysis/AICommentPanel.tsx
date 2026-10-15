import React, { useState, useEffect, useCallback } from "react";
import {
  Sparkles,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Cpu,
  ShieldCheck,
  ShieldAlert,
  Copy,
  Check,
} from "lucide-react";
import {
  apiClient,
  type AICommentResponse,
  type AIQuotaResponse,
} from "../../api/client";

interface AICommentPanelProps {
  symbol: string;
  tf: string;
}

export const AICommentPanel: React.FC<AICommentPanelProps> = ({ symbol, tf }) => {
  const [data, setData] = useState<AICommentResponse | null>(null);
  const [quota, setQuota] = useState<AIQuotaResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isRequesting, setIsRequesting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  // Normalize symbol query
  const querySymbol = symbol === "XAUUSDT" ? "XAUUSD" : symbol;

  const fetchLatestComment = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await apiClient.GET("/api/analysis/{symbol}/ai", {
        params: {
          path: { symbol: querySymbol },
          query: { tf },
        },
      });

      if (res.data) {
        setData(res.data as AICommentResponse);
      }
    } catch {
      // It's normal if no comment generated yet
    } finally {
      setIsLoading(false);
    }
  }, [querySymbol, tf]);

  const fetchQuota = useCallback(async () => {
    try {
      const res = await apiClient.GET("/api/ai/quota");
      if (res.data) {
        setQuota(res.data as AIQuotaResponse);
      }
    } catch {
      // Non-critical
    }
  }, []);

  useEffect(() => {
    fetchLatestComment();
    fetchQuota();
  }, [fetchLatestComment, fetchQuota]);

  const handleRequestAnalysis = async () => {
    setIsRequesting(true);
    setErrorMsg(null);
    try {
      const res = await apiClient.POST("/api/analysis/{symbol}/ai", {
        params: {
          path: { symbol: querySymbol },
          query: { tf },
        },
      });

      if (res.data) {
        setData(res.data as AICommentResponse);
        fetchQuota();
      } else if (res.error) {
        setErrorMsg("Gagal mendapatkan komentar AI. Silakan coba beberapa saat lagi.");
      }
    } catch {
      setErrorMsg("Koneksi gagal atau kuota terlampaui.");
    } finally {
      setIsRequesting(false);
    }
  };

  const handleCopySummary = () => {
    if (!data?.comment) return;
    const text = `TradeRadar AI (${data.symbol} ${data.tf})\nBias: ${data.comment.bias.toUpperCase()} (${data.comment.keyakinan})\n\n${data.comment.ringkasan}\n\nInvalidasi: ${data.comment.invalidasi}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const comment = data?.comment;
  const isQuotaExceeded = quota ? quota.rpd_remaining <= 0 || quota.rpm_remaining <= 0 : false;

  return (
    <div className="p-4 rounded-xl bg-surface border border-border shadow-sm space-y-4">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-3">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-fg tracking-wide flex items-center gap-2">
              Tanggapan AI
              {data && (
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono border ${
                    data.is_fallback
                      ? "bg-amber-500/10 border-amber-500/20 text-amber-400"
                      : "bg-purple-500/10 border-purple-500/20 text-purple-400"
                  }`}
                >
                  {data.is_fallback ? "Komentar Otomatis (Template)" : data.model || "Gemini Flash"}
                </span>
              )}
            </h3>
            <p className="text-[11px] text-muted">
              Analisis naratif kontekstual berbasis data matematis
            </p>
          </div>
        </div>

        {/* Action Button & Quota Info */}
        <div className="flex items-center gap-2">
          {quota && (
            <span
              className="text-[10px] font-mono text-muted hidden sm:inline-block"
              title={`Batas per menit: ${quota.rpm_remaining}/${quota.rpm_limit} | Batas per hari: ${quota.rpd_remaining}/${quota.rpd_limit}`}
            >
              Kuota: {quota.rpd_remaining} sisa
            </span>
          )}

          <button
            type="button"
            onClick={handleRequestAnalysis}
            disabled={isRequesting || isQuotaExceeded}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm ${
              isQuotaExceeded
                ? "bg-surface-2 text-muted border border-border cursor-not-allowed"
                : "bg-accent hover:bg-accent/90 text-accent-fg active:scale-95"
            }`}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRequesting ? "animate-spin" : ""}`} />
            <span>{isRequesting ? "Menganalisa..." : "Minta Analisa AI"}</span>
          </button>
        </div>
      </div>

      {/* Error Notice */}
      {errorMsg && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && !data && (
        <div className="py-8 flex flex-col items-center justify-center text-muted gap-2 animate-pulse">
          <Cpu className="w-6 h-6 text-purple-400 animate-bounce" />
          <span className="text-xs">Memuat tanggapan AI...</span>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !data && (
        <div className="p-6 text-center rounded-xl bg-surface-2/30 border border-dashed border-border/80 space-y-2">
          <Sparkles className="w-8 h-8 text-muted/60 mx-auto" />
          <p className="text-xs font-medium text-fg">Belum Ada Analisis AI</p>
          <p className="text-[11px] text-muted max-w-sm mx-auto">
            Klik tombol <strong>Minta Analisa AI</strong> untuk mendapatkan ulasan naratif terstruktur
            mengenai konfluensi indikator, skenario pasar, dan level penting.
          </p>
        </div>
      )}

      {/* Structured AI Content */}
      {comment && (
        <div className="space-y-4 text-xs">
          {/* Top Chips Row: Bias, Keyakinan, Engine Agreement */}
          <div className="flex flex-wrap items-center justify-between gap-2 bg-surface-2/40 p-2.5 rounded-lg border border-border">
            <div className="flex items-center gap-2">
              {/* Bias Badge */}
              <span
                className={`px-2.5 py-1 rounded text-xs font-bold font-mono uppercase flex items-center gap-1 border ${
                  comment.bias === "bullish"
                    ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400"
                    : comment.bias === "bearish"
                    ? "bg-rose-500/15 border-rose-500/30 text-rose-400"
                    : "bg-amber-500/15 border-amber-500/30 text-amber-400"
                }`}
              >
                {comment.bias === "bullish" && <TrendingUp className="w-3.5 h-3.5" />}
                {comment.bias === "bearish" && <TrendingDown className="w-3.5 h-3.5" />}
                {comment.bias === "netral" && <Minus className="w-3.5 h-3.5" />}
                {comment.bias}
              </span>

              {/* Keyakinan Chip */}
              <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-surface border border-border text-muted">
                Keyakinan:{" "}
                <strong className="text-fg capitalize">{comment.keyakinan}</strong>
              </span>
            </div>

            {/* Engine Agreement Indicator */}
            <div className="flex items-center gap-1.5">
              {comment.setuju_dengan_engine ? (
                <div className="flex items-center gap-1 text-emerald-400 font-medium text-[11px]">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Sepakat Sinyal Engine</span>
                </div>
              ) : (
                <div className="flex items-center gap-1 text-amber-400 font-medium text-[11px]">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Divergensi AI vs Engine</span>
                </div>
              )}

              <button
                type="button"
                onClick={handleCopySummary}
                className="p-1 rounded hover:bg-surface text-muted hover:text-fg transition-colors ml-1"
                title="Salin rangkuman"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>

          {/* Ringkasan */}
          <div className="p-3 rounded-lg bg-surface-2/30 border border-border">
            <h4 className="text-[11px] font-bold text-fg uppercase tracking-wider mb-1 text-muted">
              Ringkasan Naratif
            </h4>
            <p className="text-xs text-fg leading-relaxed">{comment.ringkasan}</p>
          </div>

          {/* Skenario Bullish vs Bearish */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20 space-y-1">
              <div className="flex items-center gap-1.5 text-emerald-400 font-bold text-[11px]">
                <TrendingUp className="w-3.5 h-3.5" />
                <span>Skenario Bullish</span>
              </div>
              <p className="text-[11px] text-fg/90 leading-relaxed">
                {comment.skenario_bullish}
              </p>
            </div>

            <div className="p-3 rounded-lg bg-rose-500/5 border border-rose-500/20 space-y-1">
              <div className="flex items-center gap-1.5 text-rose-400 font-bold text-[11px]">
                <TrendingDown className="w-3.5 h-3.5" />
                <span>Skenario Bearish</span>
              </div>
              <p className="text-[11px] text-fg/90 leading-relaxed">
                {comment.skenario_bearish}
              </p>
            </div>
          </div>

          {/* Alasan Utama & Risiko */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Alasan Utama */}
            <div className="p-3 rounded-lg bg-surface-2/20 border border-border space-y-2">
              <div className="flex items-center gap-1.5 text-fg font-semibold text-[11px]">
                <ShieldCheck className="w-3.5 h-3.5 text-accent" />
                <span>Alasan Utama</span>
              </div>
              <ul className="space-y-1 text-[11px] text-muted">
                {comment.alasan_utama.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-1.5">
                    <span className="text-accent">•</span>
                    <span className="leading-tight">{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Risiko / Kontradiksi */}
            <div className="p-3 rounded-lg bg-surface-2/20 border border-border space-y-2">
              <div className="flex items-center gap-1.5 text-fg font-semibold text-[11px]">
                <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                <span>Faktor Risiko</span>
              </div>
              <ul className="space-y-1 text-[11px] text-muted">
                {comment.risiko.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-1.5">
                    <span className="text-amber-400">•</span>
                    <span className="leading-tight">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Level Penting Chips */}
          {comment.level_penting && comment.level_penting.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-[11px] font-bold uppercase text-muted tracking-wide">
                Level Kunci Terverifikasi
              </span>
              <div className="flex flex-wrap gap-1.5">
                {comment.level_penting.map((lvl, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded font-mono font-semibold text-xs bg-surface-2 border border-border text-fg shadow-xs"
                  >
                    {lvl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Invalidasi & Saran Manajemen */}
          <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20 space-y-2">
            <div>
              <span className="text-[10px] font-bold uppercase text-amber-400 block tracking-wider">
                Kondisi Invalidasi Tesis
              </span>
              <p className="text-[11px] text-fg mt-0.5 leading-relaxed">{comment.invalidasi}</p>
            </div>
            <div className="pt-2 border-t border-amber-500/10">
              <span className="text-[10px] font-bold uppercase text-muted block tracking-wider">
                Saran Manajemen Risiko
              </span>
              <p className="text-[11px] text-muted mt-0.5 leading-relaxed">
                {comment.saran_manajemen}
              </p>
            </div>
          </div>

          {/* Footer Metadata: Latency, Timestamp, Tokens */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-border/50 text-[10px] text-muted font-mono">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3 text-muted/70" />
                {new Date(data.created_at).toLocaleTimeString("id-ID", {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                  timeZone: "Asia/Jakarta",
                })}{" "}
                WIB
              </span>
              <span>Latensi: {(data.latency_ms / 1000).toFixed(2)}s</span>
            </div>

            <div className="flex items-center gap-2">
              {data.tokens_in > 0 && <span>Tokens: {data.tokens_in} in / {data.tokens_out} out</span>}
              <span className="px-1.5 py-0.2 rounded bg-surface-2 text-muted">
                {data.provider}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
