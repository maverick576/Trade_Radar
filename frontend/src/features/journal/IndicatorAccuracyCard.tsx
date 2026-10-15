import React from "react";
import { Gauge, ArrowUpRight, ArrowDownRight } from "lucide-react";
import type { IndicatorAccuracyItem } from "../../api/client";
import { formatIdNumber } from "../tickets/formatTicket";

interface IndicatorAccuracyCardProps {
  items: IndicatorAccuracyItem[];
  isLoading?: boolean;
}

export const IndicatorAccuracyCard: React.FC<IndicatorAccuracyCardProps> = ({
  items,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="p-5 rounded-2xl bg-surface border border-border h-72 animate-pulse flex items-center justify-center text-muted text-sm">
        Memuat akurasi indikator...
      </div>
    );
  }

  if (!items || items.length === 0) {
    return (
      <div className="p-6 rounded-2xl bg-surface border border-border flex flex-col items-center justify-center h-56 text-center">
        <Gauge className="w-10 h-10 text-muted/50 mb-2" />
        <h3 className="text-sm font-semibold text-fg">Belum Ada Riwayat Sinyal Indikator</h3>
        <p className="text-xs text-muted mt-1 max-w-sm">
          Akurasi tiap indikator akan otomatis terhitung saat trade dengan snapshot analisis ditutup.
        </p>
      </div>
    );
  }

  return (
    <div className="p-5 rounded-2xl bg-surface border border-border shadow-sm flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-accent/10 text-accent">
            <Gauge className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-fg">Akurasi per Indikator</h3>
            <p className="text-xs text-muted">
              Perbandingan winrate saat sinyal indikator searah vs berlawanan arah trade
            </p>
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1.5 text-emerald-400">
            <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500 inline-block" />
            Searah (Aligned)
          </span>
          <span className="flex items-center gap-1.5 text-amber-400">
            <span className="w-2.5 h-2.5 rounded-sm bg-amber-500 inline-block" />
            Berlawanan (Contrarian)
          </span>
        </div>
      </div>

      {/* Grid of Indicators */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
        {items.map((item, idx) => {
          const edge = item.aligned_winrate_pct - item.contrarian_winrate_pct;
          const hasSignificantEdge = edge > 5 && item.aligned_trades >= 3;
          const hasInvertedEdge = edge < -5 && item.contrarian_trades >= 3;

          return (
            <div
              key={idx}
              className="p-3.5 rounded-xl bg-surface-hover/40 border border-border/60 flex flex-col justify-between gap-2.5 hover:border-accent/40 transition-colors"
            >
              {/* Title & Edge Badge */}
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-fg">{item.indicator_name}</span>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded-md flex items-center gap-1 font-semibold ${
                    hasSignificantEdge
                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                      : hasInvertedEdge
                      ? "bg-rose-500/10 text-rose-400 border border-rose-500/30"
                      : "bg-surface text-muted border border-border"
                  }`}
                >
                  {edge > 0 ? (
                    <ArrowUpRight className="w-3 h-3 text-emerald-400" />
                  ) : edge < 0 ? (
                    <ArrowDownRight className="w-3 h-3 text-rose-400" />
                  ) : null}
                  Edge: {edge > 0 ? "+" : ""}{formatIdNumber(edge, 1)}%
                </span>
              </div>

              {/* Progress Bars Comparison */}
              <div className="flex flex-col gap-1.5">
                {/* Aligned Bar */}
                <div className="flex items-center gap-2 text-[11px] font-mono">
                  <span className="w-16 text-muted text-[10px] truncate">Searah</span>
                  <div className="flex-1 h-3 rounded bg-slate-800 overflow-hidden relative">
                    <div
                      className="h-full bg-emerald-500 rounded transition-all duration-300"
                      style={{ width: `${Math.min(100, item.aligned_winrate_pct)}%` }}
                    />
                  </div>
                  <span className="w-14 text-right font-semibold text-emerald-400">
                    {formatIdNumber(item.aligned_winrate_pct, 1)}%
                  </span>
                  <span className="w-16 text-right text-[10px] text-muted">
                    ({item.aligned_trades} trade)
                  </span>
                </div>

                {/* Contrarian Bar */}
                <div className="flex items-center gap-2 text-[11px] font-mono">
                  <span className="w-16 text-muted text-[10px] truncate">Lawan</span>
                  <div className="flex-1 h-3 rounded bg-slate-800 overflow-hidden relative">
                    <div
                      className="h-full bg-amber-500 rounded transition-all duration-300"
                      style={{ width: `${Math.min(100, item.contrarian_winrate_pct)}%` }}
                    />
                  </div>
                  <span className="w-14 text-right font-semibold text-amber-400">
                    {formatIdNumber(item.contrarian_winrate_pct, 1)}%
                  </span>
                  <span className="w-16 text-right text-[10px] text-muted">
                    ({item.contrarian_trades} trade)
                  </span>
                </div>
              </div>

              {/* R Contribution summary */}
              <div className="flex items-center justify-between text-[10px] text-muted font-mono pt-1 border-t border-border/40">
                <span>
                  Kontribusi R Searah:{" "}
                  <strong
                    className={
                      item.aligned_r_contrib >= 0 ? "text-emerald-400" : "text-rose-400"
                    }
                  >
                    {item.aligned_r_contrib >= 0 ? "+" : ""}
                    {formatIdNumber(item.aligned_r_contrib, 2)} R
                  </strong>
                </span>
                <span>
                  Kontribusi R Lawan:{" "}
                  <strong
                    className={
                      item.contrarian_r_contrib >= 0 ? "text-emerald-400" : "text-rose-400"
                    }
                  >
                    {item.contrarian_r_contrib >= 0 ? "+" : ""}
                    {formatIdNumber(item.contrarian_r_contrib, 2)} R
                  </strong>
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
