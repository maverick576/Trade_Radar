import React, { useState } from "react";
import { TrendingUp, Activity } from "lucide-react";
import type { EquityPoint } from "../../api/client";
import { formatIdNumber } from "../tickets/formatTicket";

interface JournalEquityCurveProps {
  data: EquityPoint[];
  compareData?: EquityPoint[];
  book: "paper" | "real" | "compare";
  isLoading?: boolean;
}

export const JournalEquityCurve: React.FC<JournalEquityCurveProps> = ({
  data,
  compareData = [],
  book,
  isLoading = false,
}) => {
  const [metric, setMetric] = useState<"r" | "usd">("r");
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  if (isLoading) {
    return (
      <div className="p-5 rounded-2xl bg-surface border border-border h-72 animate-pulse flex items-center justify-center text-muted text-sm">
        Memuat kurva ekuitas...
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="p-6 rounded-2xl bg-surface border border-border flex flex-col items-center justify-center h-64 text-center">
        <Activity className="w-10 h-10 text-muted/50 mb-2" />
        <h3 className="text-sm font-semibold text-fg">Belum Ada Riwayat Trade</h3>
        <p className="text-xs text-muted mt-1 max-w-sm">
          Kurva pertumbuhan modal akan otomatis tergambar setelah ada posisi yang ditutup (close).
        </p>
      </div>
    );
  }

  // Prepend baseline origin point at trade 0 (0 R, 0 USD)
  const chartData = [
    {
      trade_number: 0,
      timestamp: data[0]?.timestamp || "",
      equity_r: 0,
      equity_usd: 0,
      drawdown_r: 0,
      drawdown_pct: 0,
    },
    ...data,
  ];

  const compareChartData =
    compareData && compareData.length > 0
      ? [
          {
            trade_number: 0,
            timestamp: compareData[0]?.timestamp || "",
            equity_r: 0,
            equity_usd: 0,
            drawdown_r: 0,
            drawdown_pct: 0,
          },
          ...compareData,
        ]
      : [];

  const getValue = (pt: EquityPoint | typeof chartData[0]) =>
    metric === "r" ? pt.equity_r : pt.equity_usd;

  // Find min/max for scaling
  const allValues = [
    ...chartData.map(getValue),
    ...compareChartData.map(getValue),
  ];
  let minVal = Math.min(0, ...allValues);
  let maxVal = Math.max(0, ...allValues);
  if (minVal === maxVal) {
    minVal -= 1;
    maxVal += 1;
  }
  // Add 10% padding
  const range = maxVal - minVal;
  const yMin = minVal - range * 0.08;
  const yMax = maxVal + range * 0.08;

  const width = 800;
  const height = 260;
  const padLeft = 55;
  const padRight = 20;
  const padTop = 20;
  const padBottom = 30;

  const chartW = width - padLeft - padRight;
  const chartH = height - padTop - padBottom;

  const maxTrades = Math.max(
    chartData.length - 1,
    compareChartData.length > 0 ? compareChartData.length - 1 : 1,
    1
  );

  const getX = (tradeNum: number) => padLeft + (tradeNum / maxTrades) * chartW;
  const getY = (val: number) => padTop + chartH - ((val - yMin) / (yMax - yMin)) * chartH;
  const zeroY = getY(0);

  // Build SVG path
  const buildPath = (pts: Array<typeof chartData[0]>) => {
    if (pts.length === 0) return "";
    return pts
      .map((pt, i) => `${i === 0 ? "M" : "L"} ${getX(pt.trade_number).toFixed(1)} ${getY(getValue(pt)).toFixed(1)}`)
      .join(" ");
  };

  const primaryPath = buildPath(chartData);
  const comparePath = buildPath(compareChartData);

  // Gradient area path for primary
  const areaPath =
    chartData.length > 0
      ? `${primaryPath} L ${getX(chartData[chartData.length - 1].trade_number).toFixed(1)} ${zeroY.toFixed(1)} L ${getX(0).toFixed(1)} ${zeroY.toFixed(1)} Z`
      : "";

  const latestPt = data[data.length - 1];
  const compareLatestPt = compareData[compareData.length - 1];

  const hoveredPt = hoverIndex !== null && hoverIndex < data.length ? data[hoverIndex] : null;

  return (
    <div className="p-5 rounded-2xl bg-surface border border-border shadow-sm flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-accent/10 text-accent">
            <TrendingUp className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-fg">Kurva Ekuitas Kumulatif</h3>
            <p className="text-xs text-muted">
              Pertumbuhan portofolio per penutupan posisi ({data.length} trade)
            </p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3">
          {book === "compare" && (
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1.5 text-cyan-400">
                <span className="w-2.5 h-2.5 rounded-full bg-cyan-500 inline-block" />
                Paper
              </span>
              <span className="flex items-center gap-1.5 text-emerald-400">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />
                Real
              </span>
            </div>
          )}

          <div className="inline-flex rounded-lg bg-surface-hover p-0.5 border border-border text-xs">
            <button
              type="button"
              onClick={() => setMetric("r")}
              className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                metric === "r"
                  ? "bg-accent text-white shadow-sm"
                  : "text-muted hover:text-fg"
              }`}
            >
              R-Multiple
            </button>
            <button
              type="button"
              onClick={() => setMetric("usd")}
              className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                metric === "usd"
                  ? "bg-accent text-white shadow-sm"
                  : "text-muted hover:text-fg"
              }`}
            >
              USD ($)
            </button>
          </div>
        </div>
      </div>

      {/* Stats summary row */}
      <div className="flex flex-wrap items-center gap-4 text-xs font-mono border-b border-border/50 pb-3">
        <div>
          <span className="text-muted">Total Return: </span>
          <span
            className={`font-bold ${
              latestPt.equity_r >= 0 ? "text-emerald-400" : "text-rose-400"
            }`}
          >
            {latestPt.equity_r >= 0 ? "+" : ""}
            {metric === "r"
              ? `${formatIdNumber(latestPt.equity_r, 2)} R`
              : `$${formatIdNumber(latestPt.equity_usd, 2)}`}
          </span>
        </div>

        {book === "compare" && compareLatestPt && (
          <div>
            <span className="text-muted">Real Return: </span>
            <span
              className={`font-bold ${
                compareLatestPt.equity_r >= 0 ? "text-emerald-400" : "text-rose-400"
              }`}
            >
              {compareLatestPt.equity_r >= 0 ? "+" : ""}
              {metric === "r"
                ? `${formatIdNumber(compareLatestPt.equity_r, 2)} R`
                : `$${formatIdNumber(compareLatestPt.equity_usd, 2)}`}
            </span>
          </div>
        )}

        <div>
          <span className="text-muted">Max Drawdown: </span>
          <span className="text-amber-400 font-semibold">
            -{formatIdNumber(latestPt.drawdown_r, 2)} R (-{formatIdNumber(latestPt.drawdown_pct, 1)}%)
          </span>
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="relative w-full overflow-hidden">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto overflow-visible select-none"
        >
          <defs>
            <linearGradient id="eqAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct, idx) => {
            const y = padTop + chartH * pct;
            const val = yMax - pct * (yMax - yMin);
            return (
              <g key={idx}>
                <line
                  x1={padLeft}
                  y1={y}
                  x2={width - padRight}
                  y2={y}
                  stroke="#334155"
                  strokeWidth="0.5"
                  strokeDasharray="3 3"
                />
                <text
                  x={padLeft - 8}
                  y={y + 3.5}
                  textAnchor="end"
                  fill="#94a3b8"
                  fontSize="10"
                  fontFamily="monospace"
                >
                  {metric === "r" ? `${val.toFixed(1)}R` : `$${Math.round(val)}`}
                </text>
              </g>
            );
          })}

          {/* Zero baseline */}
          {zeroY >= padTop && zeroY <= padTop + chartH && (
            <line
              x1={padLeft}
              y1={zeroY}
              x2={width - padRight}
              y2={zeroY}
              stroke="#64748b"
              strokeWidth="1.2"
            />
          )}

          {/* Area fill */}
          {book !== "compare" && (
            <path d={areaPath} fill="url(#eqAreaGrad)" />
          )}

          {/* Primary curve */}
          <path
            d={primaryPath}
            fill="none"
            stroke={book === "compare" ? "#22d3ee" : "#38bdf8"}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Compare curve */}
          {book === "compare" && comparePath && (
            <path
              d={comparePath}
              fill="none"
              stroke="#10b981"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Interactive hover points */}
          {chartData.slice(1).map((pt, idx) => {
            const cx = getX(pt.trade_number);
            const cy = getY(getValue(pt));
            const isHovered = hoverIndex === idx;

            return (
              <g
                key={idx}
                className="cursor-pointer"
                onMouseEnter={() => setHoverIndex(idx)}
                onMouseLeave={() => setHoverIndex(null)}
              >
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 5 : 2}
                  fill={getValue(pt) >= 0 ? "#38bdf8" : "#fb7185"}
                  stroke="#0f172a"
                  strokeWidth="1.5"
                  className="transition-all"
                />
                <rect
                  x={cx - 10}
                  y={padTop}
                  width="20"
                  height={chartH}
                  fill="transparent"
                />
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip Overlay */}
        {hoveredPt && (
          <div className="absolute top-2 right-4 bg-slate-900/90 backdrop-blur-md border border-slate-700 p-2.5 rounded-lg shadow-xl text-xs font-mono z-10 pointer-events-none">
            <div className="text-muted text-[11px] mb-1">
              Trade #{hoveredPt.trade_number} ·{" "}
              {hoveredPt.timestamp
                ? new Date(hoveredPt.timestamp).toLocaleString("id-ID", {
                    timeZone: "Asia/Jakarta",
                    day: "2-digit",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "-"}
            </div>
            <div className="flex items-center gap-3">
              <div>
                <span className="text-muted">Kumulatif: </span>
                <span
                  className={`font-bold ${
                    hoveredPt.equity_r >= 0 ? "text-emerald-400" : "text-rose-400"
                  }`}
                >
                  {hoveredPt.equity_r >= 0 ? "+" : ""}
                  {formatIdNumber(hoveredPt.equity_r, 2)} R (${formatIdNumber(hoveredPt.equity_usd, 2)})
                </span>
              </div>
              <div>
                <span className="text-muted">DD: </span>
                <span className="text-amber-400">
                  -{formatIdNumber(hoveredPt.drawdown_r, 2)} R
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
