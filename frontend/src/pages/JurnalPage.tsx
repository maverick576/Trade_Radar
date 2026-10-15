import React, { useState, useEffect, useCallback } from "react";
import {
  Download,
  RefreshCw,
  BookOpen,
  AlertTriangle,
} from "lucide-react";
import {
  api,
  type JournalResponse,
  type JournalBookType,
} from "../api/client";
import { JournalBookToggle } from "../features/journal/JournalBookToggle";
import {
  JournalFilterBar,
  type JournalFilters,
} from "../features/journal/JournalFilterBar";
import { JournalKpiGrid } from "../features/journal/JournalKpiGrid";
import { JournalEquityCurve } from "../features/journal/JournalEquityCurve";
import { JournalRDistribution } from "../features/journal/JournalRDistribution";
import { JournalHeatmap } from "../features/journal/JournalHeatmap";
import { JournalBreakdowns } from "../features/journal/JournalBreakdowns";
import { IndicatorAccuracyCard } from "../features/journal/IndicatorAccuracyCard";
import { MacroFilterImpactCard } from "../features/journal/MacroFilterImpactCard";
import { RealSlippageCard } from "../features/journal/RealSlippageCard";
import { JournalTradesTable } from "../features/journal/JournalTradesTable";
import { TradeSnapshotModal } from "../features/journal/TradeSnapshotModal";

export const JurnalPage: React.FC = () => {
  const [book, setBook] = useState<JournalBookType>("paper");
  const [filters, setFilters] = useState<JournalFilters>({
    datePreset: "ALL",
    symbol: "",
    strategy: "",
  });

  const [data, setData] = useState<JournalResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<boolean>(false);
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getJournalStats({
        book,
        symbol: filters.symbol || undefined,
        strategy: filters.strategy || undefined,
        date_from: filters.dateFrom || undefined,
        date_to: filters.dateTo || undefined,
      });
      setData(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Gagal memuat statistik jurnal");
    } finally {
      setLoading(false);
    }
  }, [book, filters]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const handleExportCsv = async () => {
    setExporting(true);
    try {
      await api.exportJournalCsv({
        book,
        symbol: filters.symbol || undefined,
        strategy: filters.strategy || undefined,
        date_from: filters.dateFrom || undefined,
        date_to: filters.dateTo || undefined,
      });
    } catch (err: unknown) {
      alert("Gagal mengekspor CSV: " + (err instanceof Error ? err.message : "Terjadi kesalahan"));
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-4 md:p-6 max-w-7xl mx-auto w-full pb-16">
      {/* Page Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-2 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-2xl bg-accent/10 border border-accent/20 text-accent">
            <BookOpen className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl md:text-2xl font-bold text-fg">
              Jurnal & Statistik Winrate
            </h1>
            <p className="text-xs md:text-sm text-muted">
              Analisis performa konfluensi, transparansi akurasi indikator, dan perbandingan Paper vs Real
            </p>
          </div>
        </div>

        {/* Top Controls: Book Toggle & CSV Export */}
        <div className="flex flex-wrap items-center gap-3">
          <JournalBookToggle value={book} onChange={setBook} />

          <button
            type="button"
            onClick={handleExportCsv}
            disabled={exporting || loading}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-surface border border-border text-xs font-medium text-fg hover:bg-surface-hover hover:border-accent/40 disabled:opacity-50 transition-all shadow-sm"
            title="Ekspor CSV RFC 4180 dengan BOM UTF-8"
          >
            <Download className={`w-4 h-4 ${exporting ? "animate-bounce" : "text-accent"}`} />
            <span>{exporting ? "Mengekspor..." : "Ekspor CSV"}</span>
          </button>

          <button
            type="button"
            onClick={fetchStats}
            disabled={loading}
            className="p-2 rounded-xl bg-surface border border-border text-muted hover:text-fg hover:bg-surface-hover transition-colors"
            title="Segarkan data"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-accent" : ""}`} />
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={fetchStats}
            className="underline font-semibold hover:text-rose-300"
          >
            Coba Lagi
          </button>
        </div>
      )}

      {/* Filter Bar */}
      <JournalFilterBar filters={filters} onFilterChange={setFilters} />

      {/* Primary KPI Grid */}
      <JournalKpiGrid
        kpis={data?.kpis || null}
        compareKpis={data?.compare_kpis || null}
        book={book}
        isLoading={loading}
      />

      {/* Visual Analytics Row: Equity Curve & R-Multiple Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2">
          <JournalEquityCurve
            data={data?.equity_curve || []}
            compareData={data?.compare_equity_curve || []}
            book={book}
            isLoading={loading}
          />
        </div>
        <div className="lg:col-span-1">
          <JournalRDistribution
            trades={data?.trades || []}
            kpis={data?.kpis || null}
            isLoading={loading}
          />
        </div>
      </div>

      {/* 7x24 Day x Hour Heatmap */}
      <JournalHeatmap cells={data?.heatmap || []} isLoading={loading} />

      {/* Multi-Dimensional Breakdowns */}
      <JournalBreakdowns
        breakdowns={data?.breakdowns || {}}
        isLoading={loading}
      />

      {/* Deep Dives: Indicator Edge & Macro Filter Value */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <IndicatorAccuracyCard
          items={data?.indicator_accuracy || []}
          isLoading={loading}
        />
        <MacroFilterImpactCard
          items={data?.macro_filter_impact || []}
          isLoading={loading}
        />
      </div>

      {/* Real Execution Slippage Analysis */}
      {(book === "real" || book === "compare") && (
        <RealSlippageCard
          metrics={data?.slippage_metrics || null}
          isLoading={loading}
        />
      )}

      {/* Detailed Closed Trades Table */}
      <JournalTradesTable
        trades={data?.trades || []}
        onSelectTrade={(id) => setSelectedTradeId(id)}
        isLoading={loading}
      />

      {/* Trade Snapshot Modal Drawer */}
      <TradeSnapshotModal
        tradeId={selectedTradeId}
        onClose={() => setSelectedTradeId(null)}
      />
    </div>
  );
};
