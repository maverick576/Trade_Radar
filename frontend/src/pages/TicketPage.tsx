import React, { useState, useEffect, useCallback } from "react";
import {
  Ticket,
  Filter,
  RefreshCw,
  Search,
  Sparkles,
  ShieldAlert,
  ArrowUpRight,
} from "lucide-react";
import { apiClient, type TicketItem, type SignalItem } from "../api/client";
import { TicketCard } from "../features/tickets/TicketCard";

interface TicketPageProps {
  initialSymbol?: string;
}

export const TicketPage: React.FC<TicketPageProps> = ({ initialSymbol }) => {
  const [activeTab, setActiveTab] = useState<"ACTIVE" | "HISTORY" | "BLOCKED">("ACTIVE");
  const [selectedSymbol, setSelectedSymbol] = useState<string>(initialSymbol || "ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [blockedSignals, setBlockedSignals] = useState<SignalItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const fetchTickets = useCallback(async () => {
    try {
      const { data } = await apiClient.GET("/api/tickets", {
        params: {
          query: {
            symbol: selectedSymbol !== "ALL" ? selectedSymbol : undefined,
            limit: 50,
          },
        },
      });
      if (data) {
        setTickets(data);
      }
    } catch {
      // Ignore network errors in polling
    }
  }, [selectedSymbol]);

  const fetchBlockedSignals = useCallback(async () => {
    try {
      const { data } = await apiClient.GET("/api/signals", {
        params: {
          query: {
            symbol: selectedSymbol !== "ALL" ? selectedSymbol : undefined,
            limit: 50,
          },
        },
      });
      if (data?.signals) {
        setBlockedSignals(data.signals.filter((s) => s.status === "blocked"));
      }
    } catch {
      // Ignore
    }
  }, [selectedSymbol]);

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    await Promise.all([fetchTickets(), fetchBlockedSignals()]);
    setIsLoading(false);
  }, [fetchTickets, fetchBlockedSignals]);

  useEffect(() => {
    loadAll();
    const interval = setInterval(() => {
      fetchTickets();
      fetchBlockedSignals();
    }, 15000);
    return () => clearInterval(interval);
  }, [loadAll, fetchTickets, fetchBlockedSignals]);

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await Promise.all([fetchTickets(), fetchBlockedSignals()]);
    setIsRefreshing(false);
  };

  // Filtered tickets based on activeTab
  const filteredTickets = tickets.filter((t) => {
    if (activeTab === "ACTIVE") {
      if (t.status !== "new" && t.status !== "executed") return false;
    } else if (activeTab === "HISTORY") {
      if (t.status === "new" || t.status === "executed") return false;
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchSym = t.symbol.toLowerCase().includes(q);
      const matchStrat = t.strategy.toLowerCase().includes(q);
      const matchSide = t.side.toLowerCase().includes(q);
      if (!matchSym && !matchStrat && !matchSide) return false;
    }

    return true;
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-fg flex items-center gap-2.5">
            <Ticket className="w-7 h-7 text-accent" />
            Trade Ticket & Sinyal
          </h1>
          <p className="text-xs text-muted mt-1">
            Resume siap eksekusi terverifikasi konfluensi 10-indikator dengan level broker terkalibrasi
          </p>
        </div>

        <button
          onClick={handleManualRefresh}
          disabled={isRefreshing}
          className="px-3 py-1.5 rounded-lg bg-surface border border-border text-xs font-medium text-fg hover:bg-surface-2 transition-colors flex items-center gap-1.5 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-accent" : "text-muted"}`} />
          <span>Segarkan Data</span>
        </button>
      </div>

      {/* Control Bar: Tabs, Symbol Filter, Search */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-surface border border-border">
        {/* Main Tabs */}
        <div className="flex items-center gap-1 bg-surface-2 p-1 rounded-lg border border-border text-xs">
          <button
            onClick={() => setActiveTab("ACTIVE")}
            className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-1.5 ${
              activeTab === "ACTIVE"
                ? "bg-surface text-fg font-bold shadow-sm"
                : "text-muted hover:text-fg"
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-bull" />
            <span>Tiket Aktif</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-surface-2 text-muted">
              {tickets.filter((t) => t.status === "new" || t.status === "executed").length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("HISTORY")}
            className={`px-3 py-1.5 rounded-md transition-colors ${
              activeTab === "HISTORY"
                ? "bg-surface text-fg font-bold shadow-sm"
                : "text-muted hover:text-fg"
            }`}
          >
            <span>Riwayat Tiket</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-surface-2 text-muted ml-1.5">
              {tickets.filter((t) => t.status !== "new" && t.status !== "executed").length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("BLOCKED")}
            className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-1.5 ${
              activeTab === "BLOCKED"
                ? "bg-surface text-warn font-bold shadow-sm"
                : "text-muted hover:text-fg"
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5 text-warn" />
            <span>Sinyal Terblokir</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-warn/20 text-warn font-mono">
              {blockedSignals.length}
            </span>
          </button>
        </div>

        {/* Symbol Select & Search */}
        <div className="flex items-center gap-2 flex-1 md:flex-initial">
          <div className="flex items-center gap-1 text-xs">
            <Filter className="w-3.5 h-3.5 text-muted" />
            <select
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg bg-surface-2 border border-border text-fg text-xs focus:outline-none focus:ring-1 focus:ring-accent"
            >
              <option value="ALL">Semua Simbol</option>
              <option value="XAUUSD">XAUUSD (Gold)</option>
              <option value="BTCUSDT">BTCUSDT</option>
              <option value="ETHUSDT">ETHUSDT</option>
              <option value="SOLUSDT">SOLUSDT</option>
            </select>
          </div>

          <div className="relative flex-1 md:w-56">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Cari tiket..."
              className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-surface-2 border border-border text-xs text-fg focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      {isLoading ? (
        <div className="p-12 text-center text-muted bg-surface rounded-xl border border-border">
          <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <span className="text-sm">Memuat data tiket...</span>
        </div>
      ) : activeTab === "BLOCKED" ? (
        /* Blocked Signals Tab */
        <div className="space-y-3">
          {blockedSignals.length === 0 ? (
            <div className="p-12 text-center text-muted bg-surface rounded-xl border border-border text-xs">
              Tidak ada sinyal yang terblokir saat ini.
            </div>
          ) : (
            blockedSignals.map((sig) => (
              <div
                key={sig.id}
                className="p-4 rounded-xl bg-surface border border-warn/30 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-3"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-black text-fg">{sig.symbol}</span>
                    <span
                      className={`text-xs font-bold px-2 py-0.5 rounded ${
                        sig.side === "LONG" ? "bg-bull/20 text-bull" : "bg-bear/20 text-bear"
                      }`}
                    >
                      {sig.side}
                    </span>
                    <span className="text-xs text-muted font-mono">{sig.tf}</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-surface-2 text-muted border border-border">
                      {sig.strategy}
                    </span>
                  </div>
                  <div className="mt-2 text-xs text-warn flex items-center gap-1.5">
                    <ShieldAlert className="w-4 h-4 shrink-0" />
                    <span>
                      Dibatalkan oleh Filter:{" "}
                      <strong className="text-fg font-mono">
                        {sig.blocked_by?.join(", ") || "Macro Filter"}
                      </strong>
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span className="text-[11px] font-mono px-2 py-1 rounded bg-warn/10 text-warn border border-warn/20 flex items-center gap-1">
                    <Sparkles className="w-3 h-3" /> Disimulasikan Virtual di Paper
                  </span>
                  <a
                    href={`/analisa/${sig.symbol}`}
                    className="p-2 rounded-lg bg-surface-2 hover:bg-surface-2/80 text-muted hover:text-fg text-xs flex items-center gap-1 transition-colors"
                  >
                    Lihat Analisa <ArrowUpRight className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        /* Active or History Tickets Grid */
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filteredTickets.length === 0 ? (
            <div className="col-span-full p-12 text-center text-muted bg-surface rounded-xl border border-border text-xs">
              {activeTab === "ACTIVE"
                ? "Tidak ada tiket aktif saat ini. Tiket baru akan muncul otomatis saat sinyal STRONG_LONG atau STRONG_SHORT terkonfirmasi pada candle close M15."
                : "Belum ada riwayat tiket yang ditutup."}
            </div>
          ) : (
            filteredTickets.map((t) => (
              <TicketCard key={t.id} ticket={t} onRefresh={fetchTickets} />
            ))
          )}
        </div>
      )}
    </div>
  );
};
