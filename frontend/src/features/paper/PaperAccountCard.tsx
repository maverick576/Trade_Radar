import React from "react";
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  Target,
  Layers,
  AlertTriangle,
  CheckCircle,
} from "lucide-react";
import type { PaperAccountResponse } from "../../api/client";
import { formatIdNumber } from "../tickets/formatTicket";

interface PaperAccountCardProps {
  metrics: PaperAccountResponse | null;
  isLoading?: boolean;
}

export const PaperAccountCard: React.FC<PaperAccountCardProps> = ({
  metrics,
  isLoading = false,
}) => {
  if (isLoading || !metrics) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[...Array(5)].map((_, i) => (
          <div
            key={i}
            className="p-4 rounded-xl bg-surface border border-border animate-pulse h-24"
          />
        ))}
      </div>
    );
  }

  const pnlIsPositive = metrics.realized_pnl_usd >= 0;
  const dailyIsPositive = metrics.daily_pnl_usd >= 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
      {/* 1. Virtual Equity */}
      <div className="p-4 rounded-xl bg-surface border border-border shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-muted text-xs">
          <span>Saldo Virtual</span>
          <Wallet className="w-4 h-4 text-accent" />
        </div>
        <div className="mt-2">
          <div className="text-xl font-bold font-mono text-fg">
            ${formatIdNumber(metrics.equity, 2)}
          </div>
          <div className="text-[11px] text-muted flex items-center gap-1 mt-0.5">
            Modal: ${formatIdNumber(metrics.initial_equity, 0)}
          </div>
        </div>
      </div>

      {/* 2. PnL Realized Total */}
      <div className="p-4 rounded-xl bg-surface border border-border shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-muted text-xs">
          <span>Total PnL Realized</span>
          {pnlIsPositive ? (
            <TrendingUp className="w-4 h-4 text-bull" />
          ) : (
            <TrendingDown className="w-4 h-4 text-bear" />
          )}
        </div>
        <div className="mt-2">
          <div
            className={`text-xl font-bold font-mono ${
              pnlIsPositive ? "text-bull" : "text-bear"
            }`}
          >
            {pnlIsPositive ? "+" : ""}
            ${formatIdNumber(metrics.realized_pnl_usd, 2)}
          </div>
          <div className="text-[11px] text-muted mt-0.5">
            {metrics.total_closed_trades} trade selesai
          </div>
        </div>
      </div>

      {/* 3. PnL Hari Ini (WIB) */}
      <div className="p-4 rounded-xl bg-surface border border-border shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-muted text-xs">
          <span>PnL Hari Ini (WIB)</span>
          {dailyIsPositive ? (
            <TrendingUp className="w-4 h-4 text-bull" />
          ) : (
            <TrendingDown className="w-4 h-4 text-bear" />
          )}
        </div>
        <div className="mt-2">
          <div
            className={`text-xl font-bold font-mono ${
              dailyIsPositive ? "text-bull" : "text-bear"
            }`}
          >
            {dailyIsPositive ? "+" : ""}
            ${formatIdNumber(metrics.daily_pnl_usd, 2)}
          </div>
          <div className="text-[11px] text-muted mt-0.5">Mulai 00:00 WIB</div>
        </div>
      </div>

      {/* 4. Winrate & Expectancy */}
      <div className="p-4 rounded-xl bg-surface border border-border shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-muted text-xs">
          <span>Winrate & Expectancy</span>
          <Target className="w-4 h-4 text-accent" />
        </div>
        <div className="mt-2">
          <div className="text-xl font-bold font-mono text-fg">
            {metrics.winrate_pct.toFixed(1)}%
          </div>
          <div className="text-[11px] font-mono text-muted mt-0.5">
            Avg R:{" "}
            <span className={metrics.expectancy_r >= 0 ? "text-bull" : "text-bear"}>
              {metrics.expectancy_r >= 0 ? "+" : ""}
              {metrics.expectancy_r.toFixed(2)}R
            </span>
          </div>
        </div>
      </div>

      {/* 5. Posisi Terbuka & Risk Limit */}
      <div className="p-4 rounded-xl bg-surface border border-border shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-muted text-xs">
          <span>Posisi / Batas Harian</span>
          <Layers className="w-4 h-4 text-muted" />
        </div>
        <div className="mt-2">
          <div className="text-xl font-bold font-mono text-fg">
            {metrics.open_positions_count} / 3 <span className="text-xs font-normal text-muted">posisi</span>
          </div>
          <div className="mt-0.5">
            {metrics.daily_loss_limit_hit ? (
              <span className="text-[11px] font-semibold text-bear flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Batas 3% Tercapai (Jeda)
              </span>
            ) : (
              <span className="text-[11px] text-bull flex items-center gap-1 font-medium">
                <CheckCircle className="w-3 h-3" /> Risk Limit Normal
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
