import React, { useEffect, useRef, useState } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
  ColorType,
} from "lightweight-charts";
import { useTheme } from "../../context/ThemeContext";

export interface ChartCandle {
  open_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  is_closed?: boolean;
}

interface TradingViewChartProps {
  candles: ChartCandle[];
  liveCandle?: ChartCandle | null;
  symbol: string;
  tf: string;
}

export const TradingViewChart: React.FC<TradingViewChartProps> = ({
  candles,
  liveCandle,
  symbol,
  tf,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const candlesRef = useRef<ChartCandle[]>(candles);
  candlesRef.current = candles;

  const { theme } = useTheme();
  const [legendInfo, setLegendInfo] = useState<{
    time?: string;
    open?: number;
    high?: number;
    low?: number;
    close?: number;
    volume?: number;
    change?: number;
  } | null>(null);

  const isDark = theme === "dark" || (theme === "auto" && window.matchMedia("(prefers-color-scheme: dark)").matches);

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const bg = isDark ? "#0E1726" : "#FFFFFF";
    const textCol = isDark ? "#94A3B8" : "#64748B";
    const gridCol = isDark ? "rgba(30, 41, 59, 0.5)" : "rgba(226, 232, 240, 0.7)";
    const borderCol = isDark ? "#1E293B" : "#E2E8F0";

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight || 450,
      layout: {
        background: { type: ColorType.Solid, color: bg },
        textColor: textCol,
        fontFamily: "'JetBrains Mono', 'Inter', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: gridCol },
        horzLines: { color: gridCol },
      },
      crosshair: {
        vertLine: {
          color: isDark ? "#64748B" : "#94A3B8",
          width: 1,
          style: 1, // Dotted
        },
        horzLine: {
          color: isDark ? "#64748B" : "#94A3B8",
          width: 1,
          style: 1,
        },
      },
      rightPriceScale: {
        borderColor: borderCol,
        scaleMargins: {
          top: 0.1,
          bottom: 0.2,
        },
      },
      timeScale: {
        borderColor: borderCol,
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#10B981",
      downColor: "#EF4444",
      borderUpColor: "#10B981",
      borderDownColor: "#EF4444",
      wickUpColor: "#10B981",
      wickDownColor: "#EF4444",
    });

    const volumeSeries = chart.addHistogramSeries({
      color: "#64748B",
      priceFormat: {
        type: "volume",
      },
      priceScaleId: "", // Overlay on separate internal scale
    });

    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.82,
        bottom: 0,
      },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    // Crosshair legend handler
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData.get(candleSeries)) {
        // Fallback to latest
        const currentCandles = candlesRef.current;
        if (currentCandles.length > 0) {
          const last = currentCandles[currentCandles.length - 1];
          setLegendInfo({
            open: last.open,
            high: last.high,
            low: last.low,
            close: last.close,
            volume: last.volume,
            change: ((last.close - last.open) / last.open) * 100,
          });
        }
        return;
      }

      const cData = param.seriesData.get(candleSeries) as {
        open: number;
        high: number;
        low: number;
        close: number;
      };
      const vData = param.seriesData.get(volumeSeries) as { value: number };

      if (cData) {
        setLegendInfo({
          open: cData.open,
          high: cData.high,
          low: cData.low,
          close: cData.close,
          volume: vData?.value,
          change: ((cData.close - cData.open) / cData.open) * 100,
        });
      }
    });

    // Resize observer
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight || 450,
        });
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
  }, [isDark]);

  // Feed candle data
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current || candles.length === 0) return;

    // Sort by time and deduplicate
    const sorted = [...candles].sort(
      (a, b) => new Date(a.open_time).getTime() - new Date(b.open_time).getTime()
    );

    const candleMap = new Map<number, ChartCandle>();
    for (const c of sorted) {
      const t = Math.floor(new Date(c.open_time).getTime() / 1000);
      candleMap.set(t, c);
    }

    const candleChartData = Array.from(candleMap.entries()).map(([t, c]) => ({
      time: t as UTCTimestamp,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    const volumeChartData = Array.from(candleMap.entries()).map(([t, c]) => ({
      time: t as UTCTimestamp,
      value: c.volume,
      color: c.close >= c.open ? "rgba(16, 185, 129, 0.4)" : "rgba(239, 68, 68, 0.4)",
    }));

    candleSeriesRef.current.setData(candleChartData);
    volumeSeriesRef.current.setData(volumeChartData);

    // Initial legend
    const last = sorted[sorted.length - 1];
    setLegendInfo({
      open: last.open,
      high: last.high,
      low: last.low,
      close: last.close,
      volume: last.volume,
      change: ((last.close - last.open) / last.open) * 100,
    });

    chartRef.current?.timeScale().fitContent();
  }, [candles]);

  // Update live candle smoothly
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current || !liveCandle) return;

    const t = Math.floor(new Date(liveCandle.open_time).getTime() / 1000) as UTCTimestamp;
    candleSeriesRef.current.update({
      time: t,
      open: liveCandle.open,
      high: liveCandle.high,
      low: liveCandle.low,
      close: liveCandle.close,
    });

    volumeSeriesRef.current.update({
      time: t,
      value: liveCandle.volume,
      color: liveCandle.close >= liveCandle.open ? "rgba(16, 185, 129, 0.5)" : "rgba(239, 68, 68, 0.5)",
    });

    setLegendInfo({
      open: liveCandle.open,
      high: liveCandle.high,
      low: liveCandle.low,
      close: liveCandle.close,
      volume: liveCandle.volume,
      change: ((liveCandle.close - liveCandle.open) / liveCandle.open) * 100,
    });
  }, [liveCandle]);

  return (
    <div className="relative w-full h-[480px] bg-surface rounded-xl border border-border overflow-hidden flex flex-col">
      {/* Chart Top Bar Legend */}
      <div className="px-4 py-2 border-b border-border bg-surface-2/60 backdrop-blur flex flex-wrap items-center justify-between text-xs font-mono gap-2 z-10">
        <div className="flex items-center gap-3">
          <span className="font-bold text-fg tracking-wide">{symbol}</span>
          <span className="px-1.5 py-0.5 rounded bg-surface border border-border text-accent font-semibold">
            {tf}
          </span>
          {legendInfo && (
            <div className="hidden sm:flex items-center gap-3 text-muted">
              <span>
                O: <strong className="text-fg">{legendInfo.open?.toFixed(2)}</strong>
              </span>
              <span>
                H: <strong className="text-fg">{legendInfo.high?.toFixed(2)}</strong>
              </span>
              <span>
                L: <strong className="text-fg">{legendInfo.low?.toFixed(2)}</strong>
              </span>
              <span>
                C: <strong className="text-fg">{legendInfo.close?.toFixed(2)}</strong>
              </span>
              {legendInfo.change !== undefined && (
                <span
                  className={
                    legendInfo.change >= 0 ? "text-emerald-500 font-semibold" : "text-rose-500 font-semibold"
                  }
                >
                  {legendInfo.change >= 0 ? "+" : ""}
                  {legendInfo.change.toFixed(2)}%
                </span>
              )}
            </div>
          )}
        </div>

        {/* Live indicator tag */}
        <div className="flex items-center gap-1.5 text-xs text-muted">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Real-time Binance</span>
        </div>
      </div>

      {/* Chart Canvas Area */}
      <div ref={chartContainerRef} className="flex-1 w-full relative" />
    </div>
  );
};
