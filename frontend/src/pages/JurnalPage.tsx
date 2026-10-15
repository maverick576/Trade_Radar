import React, { useState, useEffect, useCallback } from "react";
import { BookOpen, AlertTriangle } from "lucide-react";
import {
  api,
  type JournalResponse,
  type JournalBookType,
} from "../api/client";
import { JournalBookToggle } from "../features/journal/JournalBookToggle";
import { JournalFilterBar } from "../features/journal/JournalFilterBar";
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
  const [range, setRange] = useState<string>("all");
  const [selectedSymbol, setSelectedSymbol] = useState<string>("");
  const [selectedStrategy, setSelectedStrategy] = useState<string>("");

  const [data, setData] = useState<JournalResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<boolean>(false);
  const [selectedTradeId, setSelectedTradeId] = useState<number | null>(null);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getJournalStats({
        book,
        range_str: range,
        symbol: selectedSymbol || undefined,
        strategy: selectedStrategy || undefined,
      });
      setData(res);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Gagal memuat statistik jurnal"
      );
    } finally {
      setLoading(false);
    }
  }, [book, range, selectedSymbol, selectedStrategy]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const handleExportCsv = async () => {
    setExporting(true);
    try {
      await api.exportJournalCsv({
        book,
        range_str: range,
        symbol: selectedSymbol || undefined,
        strategy: selectedStrategy || undefined,
      });
    } catch (err: unknown) {
      alert(
        "Gagal mengekspor CSV: " +
          (err instanceof Error ? err.message : "Terjadi kesalahan")
      );
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

        {/* Top Controls: Book Toggle */}
        <div className="flex flex-wrap items-center gap-3">
          <JournalBookToggle value={book} onChange={setBook} />
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

      {/* Filter Bar with presets, symbol, strategy, and CSV export */}
      <JournalFilterBar
        range={range}
        onSelectRange={setRange}
        selectedSymbol={selectedSymbol}
        onSelectSymbol={setSelectedSymbol}
        selectedStrategy={selectedStrategy}
        onSelectStrategy={setSelectedStrategy}
        onRefresh={fetchStats}
        onExportCsv={handleExportCsv}
        isExporting={exporting}
        isLoading={loading}
      />

      {/* Primary KPI Grid */}
      <JournalKpiGrid
        kpis={data?.kpis || null}
        compareKpis={
          book === "compare"
            ? data?.compare_real_kpis || null
            : null
        }
        book={book}
        isLoading={loading}
      />

      {/* Visual Analytics Row: Equity Curve & R-Multiple Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2">
          <JournalEquityCurve
            data={data?.equity_curve || []}
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
