import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
  ColorType,
  LineStyle,
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

export interface VwapPoint {
  time: number;
  vwap: number;
  upper_1: number;
  lower_1: number;
  upper_2: number;
  lower_2: number;
}

export interface EmaRibbonPoint {
  time: number;
  ema8: number;
  ema13: number;
  ema21: number;
  ema34: number;
  ema55: number;
}

export interface SupertrendPoint {
  time: number;
  supertrend: number;
  direction: number;
}

export interface BollingerPoint {
  time: number;
  mid: number;
  upper: number;
  lower: number;
  percent_b: number;
  is_squeeze: boolean;
}

export interface RsiPoint {
  time: number;
  value: number;
}

export interface CvdPoint {
  time: number;
  cvd: number;
  delta: number;
}

export interface ChartOverlays {
  vwap?: VwapPoint[];
  ema_ribbon?: EmaRibbonPoint[];
  supertrend?: SupertrendPoint[];
  bollinger?: BollingerPoint[];
}

export interface ChartPanes {
  rsi?: RsiPoint[];
  cvd?: CvdPoint[];
}

interface TradingViewChartProps {
  candles: ChartCandle[];
  liveCandle?: ChartCandle | null;
  symbol: string;
  tf: string;
  overlays?: ChartOverlays;
  panes?: ChartPanes;
  activeOverlays?: {
    vwap: boolean;
    ema_ribbon: boolean;
    supertrend: boolean;
    bollinger: boolean;
  };
  activePanes?: {
    rsi: boolean;
    cvd: boolean;
  };
  onToggleOverlay?: (key: "vwap" | "ema_ribbon" | "supertrend" | "bollinger") => void;
  onTogglePane?: (key: "rsi" | "cvd") => void;
}

export const TradingViewChart: React.FC<TradingViewChartProps> = ({
  candles,
  liveCandle,
  symbol,
  tf,
  overlays,
  panes,
  activeOverlays = { vwap: true, ema_ribbon: false, supertrend: true, bollinger: false },
  activePanes = { rsi: true, cvd: false },
  onToggleOverlay,
  onTogglePane,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const rsiContainerRef = useRef<HTMLDivElement>(null);
  const cvdContainerRef = useRef<HTMLDivElement>(null);

  const mainChartRef = useRef<IChartApi | null>(null);
  const rsiChartRef = useRef<IChartApi | null>(null);
  const cvdChartRef = useRef<IChartApi | null>(null);

  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  // Overlay Series Refs
  const vwapSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const vwapUp1Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const vwapDn1Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const vwapUp2Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const vwapDn2Ref = useRef<ISeriesApi<"Line"> | null>(null);

  const ema8Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ema13Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ema21Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ema34Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ema55Ref = useRef<ISeriesApi<"Line"> | null>(null);

  const supertrendRef = useRef<ISeriesApi<"Line"> | null>(null);

  const bbMidRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbUpRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbDnRef = useRef<ISeriesApi<"Line"> | null>(null);

  // Sub-pane Series Refs
  const rsiSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const cvdSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const cvdDeltaSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const candlesRef = useRef<ChartCandle[]>(candles);
  candlesRef.current = candles;

  const { theme } = useTheme();
  const [legendInfo, setLegendInfo] = useState<{
    open?: number;
    high?: number;
    low?: number;
    close?: number;
    volume?: number;
    change?: number;
  } | null>(null);

  const [activeRsiVal, setActiveRsiVal] = useState<number | null>(null);
  const [activeCvdVal, setActiveCvdVal] = useState<number | null>(null);

  const isDark =
    theme === "dark" ||
    (theme === "auto" && window.matchMedia("(prefers-color-scheme: dark)").matches);

  const bg = isDark ? "#0E1726" : "#FFFFFF";
  const textCol = isDark ? "#94A3B8" : "#64748B";
  const gridCol = isDark ? "rgba(30, 41, 59, 0.5)" : "rgba(226, 232, 240, 0.7)";
  const borderCol = isDark ? "#1E293B" : "#E2E8F0";

  // Synchronize logical range between charts
  const syncRange = useCallback((sourceChart: IChartApi, targetCharts: (IChartApi | null)[]) => {
    sourceChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (!range) return;
      for (const target of targetCharts) {
        if (target) {
          target.timeScale().setVisibleLogicalRange(range);
        }
      }
    });
  }, []);

  // Initialize Main Chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const mainChart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 420,
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
        vertLine: { color: isDark ? "#64748B" : "#94A3B8", width: 1, style: LineStyle.Dotted },
        horzLine: { color: isDark ? "#64748B" : "#94A3B8", width: 1, style: LineStyle.Dotted },
      },
      rightPriceScale: {
        borderColor: borderCol,
        scaleMargins: { top: 0.08, bottom: 0.18 },
      },
      timeScale: {
        borderColor: borderCol,
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const candleSeries = mainChart.addCandlestickSeries({
      upColor: "#10B981",
      downColor: "#EF4444",
      borderUpColor: "#10B981",
      borderDownColor: "#EF4444",
      wickUpColor: "#10B981",
      wickDownColor: "#EF4444",
    });

    const volumeSeries = mainChart.addHistogramSeries({
      color: "#64748B",
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });

    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    mainChartRef.current = mainChart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    // Crosshair handler for main chart
    mainChart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData.get(candleSeries)) {
        const curCandles = candlesRef.current;
        if (curCandles.length > 0) {
          const last = curCandles[curCandles.length - 1];
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

    const handleResize = () => {
      if (chartContainerRef.current && mainChartRef.current) {
        mainChartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      mainChart.remove();
      mainChartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
  }, [bg, textCol, gridCol, borderCol, isDark]);

  // Initialize RSI Pane Chart
  useEffect(() => {
    if (!activePanes.rsi || !rsiContainerRef.current) {
      if (rsiChartRef.current) {
        rsiChartRef.current.remove();
        rsiChartRef.current = null;
        rsiSeriesRef.current = null;
      }
      return;
    }

    const rsiChart = createChart(rsiContainerRef.current, {
      width: rsiContainerRef.current.clientWidth,
      height: 120,
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

    const rsiSeries = rsiChart.addLineSeries({
      color: "#8B5CF6",
      lineWidth: 2,
      priceFormat: { type: "custom", formatter: (val: number) => val.toFixed(1) },
    });

    // Reference lines for RSI 70, 50, 30
    rsiSeries.createPriceLine({
      price: 70,
      color: "rgba(239, 68, 68, 0.6)",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: "70 OB",
    });
    rsiSeries.createPriceLine({
      price: 50,
      color: "rgba(100, 116, 139, 0.4)",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      axisLabelVisible: false,
      title: "50",
    });
    rsiSeries.createPriceLine({
      price: 30,
      color: "rgba(16, 185, 129, 0.6)",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: "30 OS",
    });

    rsiChartRef.current = rsiChart;
    rsiSeriesRef.current = rsiSeries;

    // Synchronize time scales
    if (mainChartRef.current) {
      syncRange(mainChartRef.current, [rsiChart]);
      syncRange(rsiChart, [mainChartRef.current]);
    }

    rsiChart.subscribeCrosshairMove((param) => {
      if (param.seriesData.get(rsiSeries)) {
        const rVal = param.seriesData.get(rsiSeries) as { value: number };
        setActiveRsiVal(rVal.value);
      }
    });

    return () => {
      rsiChart.remove();
      rsiChartRef.current = null;
      rsiSeriesRef.current = null;
    };
  }, [activePanes.rsi, bg, textCol, gridCol, borderCol, syncRange]);

  // Initialize CVD Pane Chart
  useEffect(() => {
    if (!activePanes.cvd || !cvdContainerRef.current) {
      if (cvdChartRef.current) {
        cvdChartRef.current.remove();
        cvdChartRef.current = null;
        cvdSeriesRef.current = null;
        cvdDeltaSeriesRef.current = null;
      }
      return;
    }

    const cvdChart = createChart(cvdContainerRef.current, {
      width: cvdContainerRef.current.clientWidth,
      height: 120,
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

    const cvdDeltaSeries = cvdChart.addHistogramSeries({
      color: "rgba(59, 130, 246, 0.4)",
      priceScaleId: "",
    });

    const cvdSeries = cvdChart.addLineSeries({
      color: "#3B82F6",
      lineWidth: 2,
    });

    cvdChartRef.current = cvdChart;
    cvdSeriesRef.current = cvdSeries;
    cvdDeltaSeriesRef.current = cvdDeltaSeries;

    // Synchronize time scales
    if (mainChartRef.current) {
      syncRange(mainChartRef.current, [cvdChart]);
      syncRange(cvdChart, [mainChartRef.current]);
    }

    cvdChart.subscribeCrosshairMove((param) => {
      if (param.seriesData.get(cvdSeries)) {
        const cVal = param.seriesData.get(cvdSeries) as { value: number };
        setActiveCvdVal(cVal.value);
      }
    });

    return () => {
      cvdChart.remove();
      cvdChartRef.current = null;
      cvdSeriesRef.current = null;
      cvdDeltaSeriesRef.current = null;
    };
  }, [activePanes.cvd, bg, textCol, gridCol, borderCol, syncRange]);

  // Feed Candlestick & Volume Data
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current || candles.length === 0) return;

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

    const last = sorted[sorted.length - 1];
    setLegendInfo({
      open: last.open,
      high: last.high,
      low: last.low,
      close: last.close,
      volume: last.volume,
      change: ((last.close - last.open) / last.open) * 100,
    });

    mainChartRef.current?.timeScale().fitContent();
  }, [candles]);

  // Live Candle Update
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

  // Manage VWAP Overlays
  useEffect(() => {
    if (!mainChartRef.current) return;
    const chart = mainChartRef.current;

    if (activeOverlays.vwap && overlays?.vwap && overlays.vwap.length > 0) {
      if (!vwapSeriesRef.current) {
        vwapSeriesRef.current = chart.addLineSeries({ color: "#F59E0B", lineWidth: 2 });
        vwapUp1Ref.current = chart.addLineSeries({
          color: "rgba(245, 158, 11, 0.45)",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
        });
        vwapDn1Ref.current = chart.addLineSeries({
          color: "rgba(245, 158, 11, 0.45)",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
        });
        vwapUp2Ref.current = chart.addLineSeries({
          color: "rgba(245, 158, 11, 0.25)",
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
        });
        vwapDn2Ref.current = chart.addLineSeries({
          color: "rgba(245, 158, 11, 0.25)",
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
        });
      }

      vwapSeriesRef.current.setData(
        overlays.vwap.map((p) => ({ time: p.time as UTCTimestamp, value: p.vwap }))
      );
      vwapUp1Ref.current?.setData(
        overlays.vwap.map((p) => ({ time: p.time as UTCTimestamp, value: p.upper_1 }))
      );
      vwapDn1Ref.current?.setData(
        overlays.vwap.map((p) => ({ time: p.time as UTCTimestamp, value: p.lower_1 }))
      );
      vwapUp2Ref.current?.setData(
        overlays.vwap.map((p) => ({ time: p.time as UTCTimestamp, value: p.upper_2 }))
      );
      vwapDn2Ref.current?.setData(
        overlays.vwap.map((p) => ({ time: p.time as UTCTimestamp, value: p.lower_2 }))
      );
    } else {
      if (vwapSeriesRef.current) {
        chart.removeSeries(vwapSeriesRef.current);
        vwapSeriesRef.current = null;
      }
      if (vwapUp1Ref.current) {
        chart.removeSeries(vwapUp1Ref.current);
        vwapUp1Ref.current = null;
      }
      if (vwapDn1Ref.current) {
        chart.removeSeries(vwapDn1Ref.current);
        vwapDn1Ref.current = null;
      }
      if (vwapUp2Ref.current) {
        chart.removeSeries(vwapUp2Ref.current);
        vwapUp2Ref.current = null;
      }
      if (vwapDn2Ref.current) {
        chart.removeSeries(vwapDn2Ref.current);
        vwapDn2Ref.current = null;
      }
    }
  }, [activeOverlays.vwap, overlays?.vwap]);

  // Manage EMA Ribbon Overlays
  useEffect(() => {
    if (!mainChartRef.current) return;
    const chart = mainChartRef.current;

    if (activeOverlays.ema_ribbon && overlays?.ema_ribbon && overlays.ema_ribbon.length > 0) {
      if (!ema8Ref.current) {
        ema8Ref.current = chart.addLineSeries({ color: "#38BDF8", lineWidth: 1 });
        ema13Ref.current = chart.addLineSeries({ color: "#60A5FA", lineWidth: 1 });
        ema21Ref.current = chart.addLineSeries({ color: "#818CF8", lineWidth: 1 });
        ema34Ref.current = chart.addLineSeries({ color: "#A78BFA", lineWidth: 1 });
        ema55Ref.current = chart.addLineSeries({ color: "#C084FC", lineWidth: 2 });
      }

      const ribbon = overlays.ema_ribbon;
      ema8Ref.current.setData(ribbon.map((p) => ({ time: p.time as UTCTimestamp, value: p.ema8 })));
      ema13Ref.current?.setData(ribbon.map((p) => ({ time: p.time as UTCTimestamp, value: p.ema13 })));
      ema21Ref.current?.setData(ribbon.map((p) => ({ time: p.time as UTCTimestamp, value: p.ema21 })));
      ema34Ref.current?.setData(ribbon.map((p) => ({ time: p.time as UTCTimestamp, value: p.ema34 })));
      ema55Ref.current?.setData(ribbon.map((p) => ({ time: p.time as UTCTimestamp, value: p.ema55 })));
    } else {
      if (ema8Ref.current) {
        chart.removeSeries(ema8Ref.current);
        ema8Ref.current = null;
      }
      if (ema13Ref.current) {
        chart.removeSeries(ema13Ref.current);
        ema13Ref.current = null;
      }
      if (ema21Ref.current) {
        chart.removeSeries(ema21Ref.current);
        ema21Ref.current = null;
      }
      if (ema34Ref.current) {
        chart.removeSeries(ema34Ref.current);
        ema34Ref.current = null;
      }
      if (ema55Ref.current) {
        chart.removeSeries(ema55Ref.current);
        ema55Ref.current = null;
      }
    }
  }, [activeOverlays.ema_ribbon, overlays?.ema_ribbon]);

  // Manage Supertrend Overlay
  useEffect(() => {
    if (!mainChartRef.current) return;
    const chart = mainChartRef.current;

    if (activeOverlays.supertrend && overlays?.supertrend && overlays.supertrend.length > 0) {
      if (!supertrendRef.current) {
        supertrendRef.current = chart.addLineSeries({
          color: "#10B981",
          lineWidth: 2,
        });
      }

      supertrendRef.current.setData(
        overlays.supertrend.map((p) => ({
          time: p.time as UTCTimestamp,
          value: p.supertrend,
          color: p.direction === 1.0 ? "#10B981" : "#EF4444",
        }))
      );
    } else {
      if (supertrendRef.current) {
        chart.removeSeries(supertrendRef.current);
        supertrendRef.current = null;
      }
    }
  }, [activeOverlays.supertrend, overlays?.supertrend]);

  // Manage Bollinger Bands Overlay
  useEffect(() => {
    if (!mainChartRef.current) return;
    const chart = mainChartRef.current;

    if (activeOverlays.bollinger && overlays?.bollinger && overlays.bollinger.length > 0) {
      if (!bbMidRef.current) {
        bbMidRef.current = chart.addLineSeries({
          color: "#94A3B8",
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
        });
        bbUpRef.current = chart.addLineSeries({ color: "#06B6D4", lineWidth: 1 });
        bbDnRef.current = chart.addLineSeries({ color: "#06B6D4", lineWidth: 1 });
      }

      const bb = overlays.bollinger;
      bbMidRef.current.setData(bb.map((p) => ({ time: p.time as UTCTimestamp, value: p.mid })));
      bbUpRef.current?.setData(bb.map((p) => ({ time: p.time as UTCTimestamp, value: p.upper })));
      bbDnRef.current?.setData(bb.map((p) => ({ time: p.time as UTCTimestamp, value: p.lower })));
    } else {
      if (bbMidRef.current) {
        chart.removeSeries(bbMidRef.current);
        bbMidRef.current = null;
      }
      if (bbUpRef.current) {
        chart.removeSeries(bbUpRef.current);
        bbUpRef.current = null;
      }
      if (bbDnRef.current) {
        chart.removeSeries(bbDnRef.current);
        bbDnRef.current = null;
      }
    }
  }, [activeOverlays.bollinger, overlays?.bollinger]);

  // Update RSI Data
  useEffect(() => {
    if (activePanes.rsi && rsiSeriesRef.current && panes?.rsi && panes.rsi.length > 0) {
      rsiSeriesRef.current.setData(
        panes.rsi.map((p) => ({
          time: p.time as UTCTimestamp,
          value: p.value,
        }))
      );
      const lastRsi = panes.rsi[panes.rsi.length - 1]?.value;
      if (lastRsi !== undefined) setActiveRsiVal(lastRsi);
    }
  }, [activePanes.rsi, panes?.rsi]);

  // Update CVD Data
  useEffect(() => {
    if (activePanes.cvd && cvdSeriesRef.current && panes?.cvd && panes.cvd.length > 0) {
      cvdSeriesRef.current.setData(
        panes.cvd.map((p) => ({
          time: p.time as UTCTimestamp,
          value: p.cvd,
        }))
      );
      if (cvdDeltaSeriesRef.current) {
        cvdDeltaSeriesRef.current.setData(
          panes.cvd.map((p) => ({
            time: p.time as UTCTimestamp,
            value: p.delta,
            color: p.delta >= 0 ? "rgba(16, 185, 129, 0.45)" : "rgba(239, 68, 68, 0.45)",
          }))
        );
      }
      const lastCvd = panes.cvd[panes.cvd.length - 1]?.cvd;
      if (lastCvd !== undefined) setActiveCvdVal(lastCvd);
    }
  }, [activePanes.cvd, panes?.cvd]);

  return (
    <div className="flex flex-col bg-surface rounded-xl border border-border overflow-hidden shadow-sm">
      {/* Top Legend and Controls Bar */}
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
                    legendInfo.change >= 0
                      ? "text-emerald-500 font-semibold"
                      : "text-rose-500 font-semibold"
                  }
                >
                  {legendInfo.change >= 0 ? "+" : ""}
                  {legendInfo.change.toFixed(2)}%
                </span>
              )}
            </div>
          )}
        </div>

        {/* Overlay & Pane Toggle Buttons */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {/* Overlays */}
          <button
            type="button"
            onClick={() => onToggleOverlay?.("vwap")}
            className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors border ${
              activeOverlays.vwap
                ? "bg-amber-500/15 border-amber-500/40 text-amber-500 font-bold"
                : "bg-surface-2 border-border text-muted hover:text-fg"
            }`}
            title="Volume Weighted Average Price & ±1σ, ±2σ Bands"
          >
            VWAP
          </button>

          <button
            type="button"
            onClick={() => onToggleOverlay?.("ema_ribbon")}
            className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors border ${
              activeOverlays.ema_ribbon
                ? "bg-sky-500/15 border-sky-500/40 text-sky-400 font-bold"
                : "bg-surface-2 border-border text-muted hover:text-fg"
            }`}
            title="EMA Ribbon (8, 13, 21, 34, 55)"
          >
            EMA Ribbon
          </button>

          <button
            type="button"
            onClick={() => onToggleOverlay?.("supertrend")}
            className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors border ${
              activeOverlays.supertrend
                ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-400 font-bold"
                : "bg-surface-2 border-border text-muted hover:text-fg"
            }`}
            title="Supertrend ATR-10 Multiplier 3.0"
          >
            Supertrend
          </button>

          <button
            type="button"
            onClick={() => onToggleOverlay?.("bollinger")}
            className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors border ${
              activeOverlays.bollinger
                ? "bg-cyan-500/15 border-cyan-500/40 text-cyan-400 font-bold"
                : "bg-surface-2 border-border text-muted hover:text-fg"
            }`}
            title="Bollinger Bands 20, 2σ & Squeeze"
          >
            Bollinger
          </button>

          <div className="w-[1px] h-3 bg-border mx-1" />

          {/* Sub-Panes */}
          <button
            type="button"
            onClick={() => onTogglePane?.("rsi")}
            className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors border ${
              activePanes.rsi
                ? "bg-purple-500/15 border-purple-500/40 text-purple-400 font-bold"
                : "bg-surface-2 border-border text-muted hover:text-fg"
            }`}
            title="RSI 14 Pane with Divergence"
          >
            Pane: RSI
          </button>

          <button
            type="button"
            onClick={() => onTogglePane?.("cvd")}
            className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors border ${
              activePanes.cvd
                ? "bg-blue-500/15 border-blue-500/40 text-blue-400 font-bold"
                : "bg-surface-2 border-border text-muted hover:text-fg"
            }`}
            title="Cumulative Volume Delta / OBV Pane"
          >
            Pane: CVD
          </button>
        </div>
      </div>

      {/* Main Candlestick Chart Canvas */}
      <div ref={chartContainerRef} className="w-full relative min-h-[420px]" />

      {/* RSI Sub-Pane */}
      {activePanes.rsi && (
        <div className="w-full border-t border-border bg-surface-2/30 relative">
          <div className="px-4 py-1 flex items-center justify-between text-[11px] font-mono border-b border-border/50 bg-surface/50">
            <span className="text-purple-400 font-semibold">RSI (14 Wilder)</span>
            <span className="text-fg font-bold">
              {activeRsiVal !== null ? activeRsiVal.toFixed(1) : "—"}
            </span>
          </div>
          <div ref={rsiContainerRef} className="w-full h-[120px]" />
        </div>
      )}

      {/* CVD Sub-Pane */}
      {activePanes.cvd && (
        <div className="w-full border-t border-border bg-surface-2/30 relative">
          <div className="px-4 py-1 flex items-center justify-between text-[11px] font-mono border-b border-border/50 bg-surface/50">
            <span className="text-blue-400 font-semibold">CVD / OBV (Cumulative Delta)</span>
            <span className="text-fg font-bold">
              {activeCvdVal !== null ? activeCvdVal.toLocaleString() : "—"}
            </span>
          </div>
          <div ref={cvdContainerRef} className="w-full h-[120px]" />
        </div>
      )}
    </div>
  );
};
