import React, { useEffect, useRef } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
  ColorType,
  LineStyle,
} from "lightweight-charts";
import { useTheme } from "../../context/ThemeContext";

export interface ScorePoint {
  bar_time: string;
  score: number;
  verdict: string;
}

interface ScoreHistoryChartProps {
  history: ScorePoint[];
}

export const ScoreHistoryChart: React.FC<ScoreHistoryChartProps> = ({ history }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const areaSeriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const bg = isDark ? "#121722" : "#FFFFFF";
  const textCol = isDark ? "#8A93A6" : "#6B7280";
  const gridCol = isDark ? "rgba(35, 42, 58, 0.4)" : "rgba(226, 229, 234, 0.5)";
  const borderCol = isDark ? "#232A3A" : "#E2E5EA";

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 100,
      layout: {
        background: { type: ColorType.Solid, color: bg },
        textColor: textCol,
        fontFamily: "'JetBrains Mono', 'Inter', monospace",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: gridCol },
        horzLines: { color: gridCol },
      },
      rightPriceScale: {
        borderColor: borderCol,
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: borderCol,
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const areaSeries = chart.addAreaSeries({
      topColor: "rgba(34, 197, 94, 0.4)",
      bottomColor: "rgba(239, 68, 68, 0.4)",
      lineColor: "#3B82F6",
      lineWidth: 2,
    });

    // Zero baseline
    areaSeries.createPriceLine({
      price: 0,
      color: isDark ? "rgba(255, 255, 255, 0.2)" : "rgba(0, 0, 0, 0.2)",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      axisLabelVisible: false,
    });

    // Strong Buy threshold line (+55)
    areaSeries.createPriceLine({
      price: 55,
      color: "rgba(34, 197, 94, 0.4)",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: "Strong Buy (55)",
    });

    // Strong Sell threshold line (-55)
    areaSeries.createPriceLine({
      price: -55,
      color: "rgba(239, 68, 68, 0.4)",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: "Strong Sell (-55)",
    });

    chartRef.current = chart;
    areaSeriesRef.current = areaSeries;

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
        });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      areaSeriesRef.current = null;
    };
  }, [bg, textCol, gridCol, borderCol, isDark]);

  useEffect(() => {
    if (!areaSeriesRef.current || history.length === 0) return;

    // Sort ascending by time
    const sorted = [...history].sort(
      (a, b) => new Date(a.bar_time).getTime() - new Date(b.bar_time).getTime()
    );

    const data = sorted.map((pt) => ({
      time: Math.floor(new Date(pt.bar_time).getTime() / 1000) as UTCTimestamp,
      value: pt.score,
    }));

    areaSeriesRef.current.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [history]);

  return (
    <div className="space-y-1.5 p-3 rounded-xl bg-surface border border-border shadow-sm">
      <div className="flex items-center justify-between text-xs font-mono text-muted">
        <span className="font-bold uppercase tracking-wider text-[10px]">
          Riwayat Skor Konfluensi (48 Jam Terakhir)
        </span>
        <span className="text-[10px]">Rentang: -100 s/d +100</span>
      </div>
      <div ref={containerRef} className="w-full h-[100px] rounded-lg overflow-hidden" />
    </div>
  );
};
