import React from "react";
import { ShieldCheck, ShieldAlert } from "lucide-react";
import type { MacroFilterImpactItem } from "../../api/client";
import { formatIdNumber } from "../tickets/formatTicket";

interface MacroFilterImpactCardProps {
  items: MacroFilterImpactItem[];
  isLoading?: boolean;
}

export const MacroFilterImpactCard: React.FC<MacroFilterImpactCardProps> = ({
  items,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="p-5 rounded-2xl bg-surface border border-border h-64 animate-pulse flex items-center justify-center text-muted text-sm">
        Memuat evaluasi macro filter...
      </div>
    );
  }

  // Calculate overall net saved R and total blocked signals
  let totalBlocked = 0;
  let totalNetRSaved = 0;

  items.forEach((m) => {
    totalBlocked += m.blocked_count;
    totalNetRSaved += m.net_r_saved;
  });

  return (
    <div className="p-5 rounded-2xl bg-surface border border-border shadow-sm flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-fg">Nilai & Efektivitas Macro Filter (M1–M8)</h3>
            <p className="text-xs text-muted">
              Evaluasi simulasi virtual terhadap sinyal yang diblokir oleh guardrail pasar
            </p>
          </div>
        </div>

        {/* Aggregate KPI */}
        <div className="flex items-center gap-4 text-xs font-mono">
          <div>
            <span className="text-muted">Diblokir: </span>
            <strong className="text-fg">{totalBlocked} Sinyal</strong>
          </div>
          <div>
            <span className="text-muted">Net Diselamatkan: </span>
            <strong
              className={`text-sm ${
                totalNetRSaved >= 0 ? "text-emerald-400" : "text-amber-400"
              }`}
            >
              {totalNetRSaved >= 0 ? "+" : ""}
              {formatIdNumber(totalNetRSaved, 2)} R
            </strong>
          </div>
        </div>
      </div>

      {/* Rules list */}
      {items.length === 0 ? (
        <div className="h-40 flex items-center justify-center text-muted text-xs">
          Belum ada sinyal yang diblokir oleh filter makro pada rentang ini.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {items.map((rule, idx) => {
            const isEffective = rule.net_r_saved >= 0;

            return (
              <div
                key={idx}
                className="p-3.5 rounded-xl bg-surface-hover/40 border border-border/60 flex flex-col justify-between gap-2 hover:border-accent/40 transition-colors"
              >
                {/* Rule title & code */}
                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded font-mono font-bold text-xs bg-accent/15 text-accent border border-accent/20">
                    {rule.rule_code}
                  </span>
                  <span className="text-xs font-mono text-muted">
                    {rule.blocked_count}x blokir
                  </span>
                </div>

                <div className="text-xs font-medium text-fg line-clamp-1" title={rule.rule_name}>
                  {rule.rule_name}
                </div>

                {/* Simulated outcome stats */}
                <div className="flex items-center justify-between text-[11px] font-mono text-muted py-1 border-t border-b border-border/40">
                  <span className="text-emerald-400 flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    {rule.virtual_losses_prevented} Loss dicegah
                  </span>
                  <span className="text-rose-400 flex items-center gap-1">
                    <ShieldAlert className="w-3.5 h-3.5" />
                    {rule.virtual_wins_missed} Win lewat
                  </span>
                </div>

                {/* Net saved R */}
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-muted text-[10px]">Net R Saved:</span>
                  <span
                    className={`font-bold ${
                      isEffective ? "text-emerald-400" : "text-amber-400"
                    }`}
                  >
                    {rule.net_r_saved >= 0 ? "+" : ""}
                    {formatIdNumber(rule.net_r_saved, 2)} R
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
