import React from "react";
import { Zap, Building2, Layers } from "lucide-react";
import type { SlippageStats } from "../../api/client";
import { formatIdNumber } from "../tickets/formatTicket";

interface RealSlippageCardProps {
  metrics: SlippageStats | null;
  isLoading?: boolean;
}

export const RealSlippageCard: React.FC<RealSlippageCardProps> = ({
  metrics,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="p-5 rounded-2xl bg-surface border border-border h-64 animate-pulse flex items-center justify-center text-muted text-sm">
        Memuat analisis slippage...
      </div>
    );
  }

  if (!metrics || metrics.total_real_trades === 0) {
    return (
      <div className="p-6 rounded-2xl bg-surface border border-border flex flex-col items-center justify-center h-48 text-center">
        <Zap className="w-9 h-9 text-muted/50 mb-2" />
        <h3 className="text-sm font-semibold text-fg">Belum Ada Eksekusi Nyata</h3>
        <p className="text-xs text-muted mt-1 max-w-sm">
          Slippage nyata dihitung dari selisih harga fill saat eksekusi real dibandingkan harga entri pada Trade Ticket.
        </p>
      </div>
    );
  }

  const brokerEntries = Object.entries(metrics.breakdown_by_broker || {});
  const symbolEntries = Object.entries(metrics.breakdown_by_symbol || {});

  return (
    <div className="p-5 rounded-2xl bg-surface border border-border shadow-sm flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400">
            <Zap className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-fg">Analisis Slippage Eksekusi Nyata</h3>
            <p className="text-xs text-muted">
              Deviasi harga fill aktual terhadap sinyal ticket ({metrics.total_real_trades} trade real)
            </p>
          </div>
        </div>

        {/* Top KPIs */}
        <div className="flex items-center gap-4 text-xs font-mono">
          <div>
            <span className="text-muted">Total Beban: </span>
            <strong className="text-rose-400 font-bold">
              ${formatIdNumber(metrics.total_slippage_cost_usd, 2)}
            </strong>
          </div>
          <div>
            <span className="text-muted">Rata-rata: </span>
            <strong className="text-amber-400 font-bold">
              {formatIdNumber(metrics.avg_slippage_points, 2)} poin
            </strong>
          </div>
          <div>
            <span className="text-muted">Maksimal: </span>
            <strong className="text-fg font-bold">
              {formatIdNumber(metrics.max_slippage_points, 2)} poin
            </strong>
          </div>
        </div>
      </div>

      {/* Breakdowns Side-by-side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
        {/* By Broker Profile */}
        <div className="p-3.5 rounded-xl bg-surface-hover/30 border border-border/50 flex flex-col gap-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-fg">
            <Building2 className="w-3.5 h-3.5 text-accent" />
            <span>Per Profil Broker</span>
          </div>

          {brokerEntries.length === 0 ? (
            <div className="text-xs text-muted py-2">Tidak ada data broker</div>
          ) : (
            <div className="flex flex-col divide-y divide-border/30 font-mono text-xs">
              {brokerEntries.map(([broker, data]) => (
                <div key={broker} className="py-2 flex items-center justify-between">
                  <div>
                    <span className="font-semibold text-fg">{broker}</span>
                    <span className="text-[10px] text-muted ml-2">({data.count} fill)</span>
                  </div>
                  <div className="text-right">
                    <span className="text-amber-400 font-medium">
                      {formatIdNumber(data.avg_points, 2)} pt
                    </span>
                    <span className="text-rose-400 font-semibold ml-2">
                      (${formatIdNumber(data.cost_usd, 2)})
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* By Symbol */}
        <div className="p-3.5 rounded-xl bg-surface-hover/30 border border-border/50 flex flex-col gap-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-fg">
            <Layers className="w-3.5 h-3.5 text-accent" />
            <span>Per Simbol</span>
          </div>

          {symbolEntries.length === 0 ? (
            <div className="text-xs text-muted py-2">Tidak ada data simbol</div>
          ) : (
            <div className="flex flex-col divide-y divide-border/30 font-mono text-xs">
              {symbolEntries.map(([sym, data]) => (
                <div key={sym} className="py-2 flex items-center justify-between">
                  <div>
                    <span className="font-semibold text-fg">{sym}</span>
                    <span className="text-[10px] text-muted ml-2">({data.count} fill)</span>
                  </div>
                  <div className="text-right">
                    <span className="text-amber-400 font-medium">
                      {formatIdNumber(data.avg_points, 2)} pt
                    </span>
                    <span className="text-rose-400 font-semibold ml-2">
                      (${formatIdNumber(data.cost_usd, 2)})
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
