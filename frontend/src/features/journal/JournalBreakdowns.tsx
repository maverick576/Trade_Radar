import React, { useState } from "react";
import { Layers, PieChart, Clock, Award } from "lucide-react";
import type { BreakdownItem } from "../../api/client";
import { formatIdNumber } from "../tickets/formatTicket";

interface JournalBreakdownsProps {
  breakdowns: Record<string, BreakdownItem[]>;
  isLoading?: boolean;
}

type TabType = "symbol" | "strategy" | "session" | "verdict";

export const JournalBreakdowns: React.FC<JournalBreakdownsProps> = ({
  breakdowns,
  isLoading = false,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>("symbol");

  const tabs: Array<{ id: TabType; label: string; icon: React.FC<{ className?: string }> }> = [
    { id: "symbol", label: "Per Simbol", icon: Layers },
    { id: "strategy", label: "Per Strategi", icon: PieChart },
    { id: "session", label: "Per Sesi Pasar", icon: Clock },
    { id: "verdict", label: "Per Verdict", icon: Award },
  ];

  const currentItems = breakdowns[activeTab] || [];

  if (isLoading) {
    return (
      <div className="p-5 rounded-2xl bg-surface border border-border h-64 animate-pulse flex items-center justify-center text-muted text-sm">
        Memuat data breakdown...
      </div>
    );
  }

  return (
    <div className="p-5 rounded-2xl bg-surface border border-border shadow-sm flex flex-col gap-4">
      {/* Header with Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/50 pb-3">
        <div>
          <h3 className="text-sm font-semibold text-fg">Breakdown Multidimensi</h3>
          <p className="text-xs text-muted">
            Analisis profitabilitas berdasarkan simbol, strategi, sesi, dan verdict
          </p>
        </div>

        <div className="inline-flex rounded-lg bg-surface-hover p-1 border border-border">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  isActive
                    ? "bg-accent text-white shadow-sm"
                    : "text-muted hover:text-fg"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Table Content */}
      {currentItems.length === 0 ? (
        <div className="h-40 flex items-center justify-center text-muted text-xs">
          Belum ada data untuk kategori ini.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-border/60 text-muted font-mono">
                <th className="py-2.5 px-3 font-medium">Kategori</th>
                <th className="py-2.5 px-3 font-medium text-center">Total Trade</th>
                <th className="py-2.5 px-3 font-medium text-center">W / L / BE</th>
                <th className="py-2.5 px-3 font-medium text-right">Winrate</th>
                <th className="py-2.5 px-3 font-medium text-right">Net R</th>
                <th className="py-2.5 px-3 font-medium text-right">Profit Factor</th>
                <th className="py-2.5 px-3 font-medium text-right">Expectancy</th>
                <th className="py-2.5 px-3 font-medium text-right">Realized USD</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/30 font-mono">
              {currentItems.map((item, idx) => {
                const isPnlPositive = item.total_pnl_usd >= 0;
                const isRPositive = item.total_r >= 0;
                const isExpPositive = item.expectancy_r >= 0;

                return (
                  <tr key={idx} className="hover:bg-surface-hover/50 transition-colors">
                    <td className="py-2.5 px-3 font-semibold text-fg font-sans">
                      <span className="px-2 py-0.5 rounded bg-surface-hover border border-border/50">
                        {item.category || "-"}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-center text-fg">{item.trades}</td>
                    <td className="py-2.5 px-3 text-center text-muted">
                      <span className="text-emerald-400 font-semibold">{item.wins}</span> /{" "}
                      <span className="text-rose-400 font-semibold">{item.losses}</span> /{" "}
                      <span>{item.breakevens}</span>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="w-12 h-1.5 rounded-full bg-slate-800 overflow-hidden hidden sm:block">
                          <div
                            className="h-full bg-emerald-500 rounded-full"
                            style={{ width: `${Math.min(100, item.winrate_pct)}%` }}
                          />
                        </div>
                        <span className="font-semibold text-fg">
                          {formatIdNumber(item.winrate_pct, 1)}%
                        </span>
                      </div>
                    </td>
                    <td
                      className={`py-2.5 px-3 text-right font-bold ${
                        isRPositive ? "text-emerald-400" : "text-rose-400"
                      }`}
                    >
                      {isRPositive ? "+" : ""}
                      {formatIdNumber(item.total_r, 2)} R
                    </td>
                    <td className="py-2.5 px-3 text-right text-fg">
                      {item.profit_factor >= 999 ? "∞" : formatIdNumber(item.profit_factor, 2)}
                    </td>
                    <td
                      className={`py-2.5 px-3 text-right ${
                        isExpPositive ? "text-emerald-400" : "text-rose-400"
                      }`}
                    >
                      {isExpPositive ? "+" : ""}
                      {formatIdNumber(item.expectancy_r, 2)} R
                    </td>
                    <td
                      className={`py-2.5 px-3 text-right font-semibold ${
                        isPnlPositive ? "text-emerald-400" : "text-rose-400"
                      }`}
                    >
                      {isPnlPositive ? "+" : ""}${formatIdNumber(item.total_pnl_usd, 2)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
