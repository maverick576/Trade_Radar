import React from "react";
import { Download, RefreshCw, Filter } from "lucide-react";

interface JournalFilterBarProps {
  range: string;
  onSelectRange: (r: string) => void;
  selectedSymbol: string;
  onSelectSymbol: (s: string) => void;
  selectedStrategy: string;
  onSelectStrategy: (strat: string) => void;
  onRefresh: () => void;
  onExportCsv: () => void;
  isExporting?: boolean;
  isLoading?: boolean;
}

export const JournalFilterBar: React.FC<JournalFilterBarProps> = ({
  range,
  onSelectRange,
  selectedSymbol,
  onSelectSymbol,
  selectedStrategy,
  onSelectStrategy,
  onRefresh,
  onExportCsv,
  isExporting = false,
  isLoading = false,
}) => {
  const rangePresets = [
    { id: "7d", label: "7 Hari" },
    { id: "30d", label: "30 Hari" },
    { id: "90d", label: "90 Hari" },
    { id: "all", label: "Semua" },
  ];

  const symbols = [
    { value: "", label: "Semua Simbol" },
    { value: "XAUUSDT", label: "XAUUSDT (Gold)" },
    { value: "BTCUSDT", label: "BTCUSDT" },
    { value: "ETHUSDT", label: "ETHUSDT" },
    { value: "SOLUSDT", label: "SOLUSDT" },
  ];

  const strategies = [
    { value: "", label: "Semua Strategi" },
    { value: "Konfluensi-10", label: "Strategi A (Konfluensi-10)" },
    { value: "Triple-EMA", label: "Strategi B (Triple-EMA)" },
  ];

  return (
    <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3 p-3 bg-surface border border-border rounded-xl">
      {/* Left: Range presets */}
      <div className="flex items-center gap-1 overflow-x-auto pb-1 lg:pb-0">
        <span className="text-xs text-muted font-medium mr-1.5 flex items-center gap-1 shrink-0">
          <Filter className="w-3.5 h-3.5" aria-hidden="true" />
          <span>Rentang:</span>
        </span>
        {rangePresets.map((p) => (
          <button
            key={p.id}
            id={`filter-range-${p.id}`}
            type="button"
            onClick={() => onSelectRange(p.id)}
            className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors shrink-0 ${
              range === p.id
                ? "bg-accent/20 text-accent border border-accent/40 font-semibold"
                : "text-muted hover:text-fg hover:bg-surface-elevated border border-transparent"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Right: Dropdowns & Actions */}
      <div className="flex flex-wrap items-center gap-2.5">
        {/* Symbol Select */}
        <select
          id="select-journal-symbol"
          value={selectedSymbol}
          onChange={(e) => onSelectSymbol(e.target.value)}
          aria-label="Filter berdasarkan simbol"
          className="text-xs bg-bg text-fg border border-border rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-accent"
        >
          {symbols.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>

        {/* Strategy Select */}
        <select
          id="select-journal-strategy"
          value={selectedStrategy}
          onChange={(e) => onSelectStrategy(e.target.value)}
          aria-label="Filter berdasarkan strategi"
          className="text-xs bg-bg text-fg border border-border rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-accent"
        >
          {strategies.map((st) => (
            <option key={st.value} value={st.value}>
              {st.label}
            </option>
          ))}
        </select>

        {/* Refresh Button */}
        <button
          id="btn-journal-refresh"
          type="button"
          onClick={onRefresh}
          disabled={isLoading}
          aria-label="Segarkan data statistik jurnal"
          className="p-1.5 bg-surface-elevated hover:bg-border text-muted hover:text-fg rounded-lg transition-colors border border-border"
          title="Segarkan data"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-accent" : ""}`} />
        </button>

        {/* CSV Export Button */}
        <button
          id="btn-journal-export-csv"
          type="button"
          onClick={onExportCsv}
          disabled={isExporting}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-accent text-accent-fg font-medium rounded-lg text-xs hover:bg-accent/90 transition-colors shadow-sm disabled:opacity-50"
        >
          <Download className="w-3.5 h-3.5" aria-hidden="true" />
          <span>{isExporting ? "Mengunduh..." : "Ekspor CSV"}</span>
        </button>
      </div>
    </div>
  );
};
