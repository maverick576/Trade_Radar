import React, { useEffect, useState } from "react";
import {
  X,
  Gauge,
  ShieldCheck,
  ShieldAlert,
  Bot,
} from "lucide-react";
import { api, type TradeAnalysisSnapshotResponse } from "../../api/client";
import { formatIdNumber } from "../tickets/formatTicket";

interface IndicatorDetail {
  state?: string;
  direction?: string;
  value?: number | string;
}

interface MacroCheckDetail {
  passed?: boolean;
  status?: string;
}

interface TradeSnapshotModalProps {
  tradeId: string | null;
  onClose: () => void;
}

export const TradeSnapshotModal: React.FC<TradeSnapshotModalProps> = ({
  tradeId,
  onClose,
}) => {
  const [data, setData] = useState<TradeAnalysisSnapshotResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tradeId) {
      setData(null);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    api
      .getTradeSnapshot(tradeId)
      .then((res) => {
        if (isMounted) setData(res);
      })
      .catch((err) => {
        if (isMounted) setError(err.message || "Gagal memuat snapshot analisa");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [tradeId]);

  if (!tradeId) return null;

  const trade = data?.trade;
  const analysis = data?.analysis;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div
        className="w-full max-w-2xl max-h-[90vh] bg-surface border border-border rounded-2xl shadow-2xl flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between p-4 border-b border-border bg-surface-hover/30">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-accent/15 text-accent">
              <Gauge className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-fg flex items-center gap-2">
                <span>Snapshot Analisa Sinyal</span>
                {trade && (
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-mono font-semibold ${
                      trade.side === "LONG"
                        ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                        : "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                    }`}
                  >
                    {trade.side} {trade.symbol}
                  </span>
                )}
              </h3>
              <p className="text-xs text-muted">
                Kondisi teknikal & makro pasar pada saat candle entri ditutup
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-muted hover:text-fg hover:bg-surface-hover transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 overflow-y-auto space-y-4">
          {loading && (
            <div className="py-16 text-center text-muted text-sm animate-pulse">
              Memuat data snapshot analisa...
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
              {error}
            </div>
          )}

          {!loading && trade && (
            <>
              {/* Trade execution summary banner */}
              <div className="p-3.5 rounded-xl bg-surface-hover/50 border border-border flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
                <div>
                  <span className="text-muted">Buku: </span>
                  <span className="font-semibold uppercase text-accent">
                    {trade.book}
                  </span>
                </div>
                <div>
                  <span className="text-muted">Entri: </span>
                  <span className="text-fg font-semibold">{trade.entry_price}</span>
                </div>
                <div>
                  <span className="text-muted">Exit: </span>
                  <span className="text-fg font-semibold">{trade.exit_price || "-"}</span>
                </div>
                <div>
                  <span className="text-muted">Alasan: </span>
                  <span className="text-fg font-semibold">{trade.exit_reason || "-"}</span>
                </div>
                <div>
                  <span className="text-muted">Hasil: </span>
                  <span
                    className={`font-bold ${
                      trade.outcome === "WIN"
                        ? "text-emerald-400"
                        : trade.outcome === "LOSS"
                        ? "text-rose-400"
                        : "text-muted"
                    }`}
                  >
                    {trade.outcome} ({trade.pnl_r >= 0 ? "+" : ""}{formatIdNumber(trade.pnl_r, 2)}R / ${formatIdNumber(trade.pnl_usd, 2)})
                  </span>
                </div>
              </div>

              {/* Analysis Details */}
              {analysis ? (
                <div className="space-y-4">
                  {/* Score & Verdict Card */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3 rounded-xl bg-surface border border-border">
                      <div className="text-[11px] text-muted">Skor Konfluensi</div>
                      <div className="text-lg font-bold font-mono text-accent mt-1">
                        {analysis.score !== undefined ? analysis.score : "-"} / 100
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-surface border border-border">
                      <div className="text-[11px] text-muted">Verdict Sinyal</div>
                      <div className="text-sm font-bold text-fg mt-1 truncate">
                        {analysis.verdict || "NETRAL"}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-surface border border-border">
                      <div className="text-[11px] text-muted">Strategi</div>
                      <div className="text-xs font-bold text-fg mt-1">
                        {analysis.strategy || "Konfluensi 10"}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-surface border border-border">
                      <div className="text-[11px] text-muted">Versi Bobot</div>
                      <div className="text-xs font-mono text-muted mt-1">
                        {analysis.weights_version || "v1.0"}
                      </div>
                    </div>
                  </div>

                  {/* 10 Indicators Table */}
                  {analysis.indicators && Object.keys(analysis.indicators).length > 0 && (
                    <div className="rounded-xl border border-border overflow-hidden">
                      <div className="bg-surface-hover/60 px-3 py-2 text-xs font-semibold text-fg flex items-center justify-between">
                        <span>Status 10 Indikator Saat Entry</span>
                        <span className="text-[11px] text-muted font-normal">
                          {Object.keys(analysis.indicators).length} indikator terhitung
                        </span>
                      </div>
                      <div className="divide-y divide-border/40 max-h-48 overflow-y-auto">
                        {Object.entries(analysis.indicators).map(([name, rawInd]) => {
                          const ind = rawInd as IndicatorDetail;
                          const state = ind.state || ind.direction || "NEUTRAL";
                          const isBull = state.toUpperCase().includes("BULL") || state === "LONG";
                          const isBear = state.toUpperCase().includes("BEAR") || state === "SHORT";

                          return (
                            <div
                              key={name}
                              className="px-3 py-2 flex items-center justify-between text-xs hover:bg-surface-hover/30"
                            >
                              <div className="font-medium text-fg">{name}</div>
                              <div className="flex items-center gap-3 font-mono">
                                <span className="text-muted text-[11px]">
                                  {ind.value !== undefined ? formatIdNumber(Number(ind.value), 2) : ""}
                                </span>
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                                    isBull
                                      ? "bg-emerald-500/15 text-emerald-400"
                                      : isBear
                                      ? "bg-rose-500/15 text-rose-400"
                                      : "bg-surface-hover text-muted"
                                  }`}
                                >
                                  {state}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Macro Guardrail Checks */}
                  {analysis.macro_checks && Object.keys(analysis.macro_checks).length > 0 && (
                    <div className="rounded-xl border border-border overflow-hidden">
                      <div className="bg-surface-hover/60 px-3 py-2 text-xs font-semibold text-fg flex items-center justify-between">
                        <span>Pemeriksaan Macro Filter (M1–M8)</span>
                        <span className="text-[11px] text-muted font-normal">
                          Guardrail Pasar
                        </span>
                      </div>
                      <div className="p-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                        {Object.entries(analysis.macro_checks).map(([rule, rawRes]) => {
                          const res = rawRes as MacroCheckDetail | boolean;
                          const passed = res === true || (typeof res === "object" && (res?.passed === true || res?.status === "PASS"));

                          return (
                            <div
                              key={rule}
                              className="p-2 rounded bg-surface border border-border flex items-center justify-between"
                            >
                              <span className="text-muted">{rule}</span>
                              {passed ? (
                                <span className="text-emerald-400 flex items-center gap-0.5 text-[11px]">
                                  <ShieldCheck className="w-3.5 h-3.5" /> Lolos
                                </span>
                              ) : (
                                <span className="text-rose-400 flex items-center gap-0.5 text-[11px]">
                                  <ShieldAlert className="w-3.5 h-3.5" /> Blok
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* AI Explanation / Comment */}
                  {analysis.ai_comment && (
                    <div className="p-3.5 rounded-xl bg-accent/5 border border-accent/20 flex flex-col gap-1.5">
                      <div className="flex items-center gap-2 text-xs font-semibold text-accent">
                        <Bot className="w-4 h-4" />
                        <span>Komentar AI Saat Itu</span>
                      </div>
                      <p className="text-xs text-fg leading-relaxed">
                        {typeof analysis.ai_comment === "string"
                          ? analysis.ai_comment
                          : analysis.ai_comment.text || JSON.stringify(analysis.ai_comment)}
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="py-8 text-center text-muted text-xs">
                  Tidak ada catatan detail snapshot analisa untuk trade ini (trade dicatat manual atau sebelum Fase 4).
                </div>
              )}
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-3 bg-surface-hover/40 border-t border-border flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-surface border border-border text-xs font-medium text-fg hover:bg-surface-hover transition-colors"
          >
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
};
