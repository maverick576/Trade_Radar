import React, { useEffect, useState } from "react";
import {
  X,
  Gauge,
  ShieldCheck,
  ShieldAlert,
  Layers,
} from "lucide-react";
import { api, type TradeAnalysisSnapshotResponse } from "../../api/client";
import { formatIdNumber } from "../tickets/formatTicket";

interface TradeSnapshotModalProps {
  tradeId: number | string | null;
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
      .getTradeSnapshot(String(tradeId))
      .then((res) => {
        if (isMounted) setData(res);
      })
      .catch((err: unknown) => {
        if (isMounted) setError(err instanceof Error ? err.message : "Gagal memuat snapshot analisa");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [tradeId]);

  if (!tradeId) return null;

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
                {data && (
                  <span className="text-xs px-2 py-0.5 rounded-full font-mono font-semibold bg-accent/15 text-accent border border-accent/30">
                    Trade #{data.trade_id} · {data.symbol} ({data.tf})
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

          {!loading && data && (
            <div className="space-y-4">
              {/* Score & Verdict Card */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-xl bg-surface border border-border">
                  <div className="text-[11px] text-muted">Skor Konfluensi</div>
                  <div className="text-lg font-bold font-mono text-accent mt-1">
                    {data.score !== undefined ? data.score : "-"} / 100
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-surface border border-border">
                  <div className="text-[11px] text-muted">Verdict Sinyal</div>
                  <div className="text-sm font-bold text-fg mt-1 truncate">
                    {data.verdict || "NETRAL"}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-surface border border-border">
                  <div className="text-[11px] text-muted">Timeframe & Bar</div>
                  <div className="text-xs font-mono text-fg mt-1 truncate">
                    {data.tf} · {data.bar_time?.slice(11, 16) || "-"}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-surface border border-border">
                  <div className="text-[11px] text-muted">Versi Bobot</div>
                  <div className="text-xs font-mono text-muted mt-1">
                    {data.weights_version || "v1.0"}
                  </div>
                </div>
              </div>

              {/* 10 Indicators Table */}
              {data.indicators && data.indicators.length > 0 && (
                <div className="rounded-xl border border-border overflow-hidden">
                  <div className="bg-surface-hover/60 px-3 py-2 text-xs font-semibold text-fg flex items-center justify-between">
                    <span>Status Indikator Saat Entry</span>
                    <span className="text-[11px] text-muted font-normal">
                      {data.indicators.length} indikator
                    </span>
                  </div>
                  <div className="divide-y divide-border/40 max-h-48 overflow-y-auto">
                    {data.indicators.map((ind: Record<string, unknown>, idx: number) => {
                      const name = (ind.key as string) || (ind.name as string) || `Indikator #${idx + 1}`;
                      const state = ((ind.state as string) || (ind.direction as string) || "NEUTRAL").toUpperCase();
                      const isBull = state.includes("BULL") || state === "LONG";
                      const isBear = state.includes("BEAR") || state === "SHORT";
                      const strength = typeof ind.strength === "number" ? ind.strength : undefined;

                      return (
                        <div
                          key={idx}
                          className="px-3 py-2 flex items-center justify-between text-xs hover:bg-surface-hover/30"
                        >
                          <div className="font-medium text-fg">{name}</div>
                          <div className="flex items-center gap-3 font-mono">
                            {strength !== undefined && (
                              <span className="text-muted text-[11px]">
                                str: {formatIdNumber(strength, 1)}
                              </span>
                            )}
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
              {data.macro && Object.keys(data.macro).length > 0 && (
                <div className="rounded-xl border border-border overflow-hidden">
                  <div className="bg-surface-hover/60 px-3 py-2 text-xs font-semibold text-fg flex items-center justify-between">
                    <span>Pemeriksaan Macro Filter (M1–M8)</span>
                    <span className="text-[11px] text-muted font-normal">
                      Guardrail Pasar
                    </span>
                  </div>
                  <div className="p-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                    {Object.entries(data.macro).map(([rule, res]: [string, unknown]) => {
                      const passed =
                        res === true ||
                        (typeof res === "object" && res !== null && (res as Record<string, unknown>).passed === true);

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

              {/* Higher Timeframe Context */}
              {data.htf && Object.keys(data.htf).length > 0 && (
                <div className="p-3.5 rounded-xl bg-surface border border-border flex flex-col gap-1.5">
                  <div className="flex items-center gap-2 text-xs font-semibold text-fg">
                    <Layers className="w-4 h-4 text-accent" />
                    <span>Konfirmasi Higher Timeframe (H1 / H4 / D1)</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-xs font-mono pt-1">
                    {Object.entries(data.htf).map(([tf, val]: [string, unknown]) => (
                      <div key={tf} className="p-2 rounded bg-surface-hover/40 border border-border/50 text-center">
                        <div className="text-muted text-[10px] uppercase">{tf}</div>
                        <div className="text-fg font-semibold mt-0.5">{String(val)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
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
