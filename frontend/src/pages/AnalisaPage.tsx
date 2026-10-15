import React, { useEffect, useState, useCallback, useRef } from "react";
import {
  AlertTriangle,
  Clock,
  RefreshCw,
  Activity,
  Layers,
  TrendingUp,
  Gauge,
  Waves,
  BookOpen,
  Brain,
  Smile,
  Zap,
} from "lucide-react";
import type { UTCTimestamp } from "lightweight-charts";
import {
  TradingViewChart,
  type ChartCandle,
  type ChartOverlays,
  type ChartPanes,
  type SignalChartMarker,
} from "../components/chart/TradingViewChart";
import { ScoreHistoryChart, type ScorePoint } from "../components/chart/ScoreHistoryChart";
import { ScoreGauge } from "../components/ui/ScoreGauge";
import { MacroChecklist, type MacroCheckItem } from "../components/ui/MacroChecklist";
import { StrategyBPanel, type StrategyBData } from "../components/ui/StrategyBPanel";
import { useMarket } from "../context/MarketContext";
import { TicketCard } from "../features/tickets/TicketCard";
import { AICommentPanel } from "../features/analysis/AICommentPanel";
import {
  apiClient,
  type CandleItem,
  type AnalysisResponse,
  type SignalsResponse,
  type TicketItem,
} from "../api/client";

interface IndicatorResultItem {
  key: string;
  category: string;
  state: "BULL" | "BEAR" | "NEUTRAL" | "NA";
  strength: number;
  values: Record<string, number>;
  reason: string;
  live_only?: boolean;
}

interface IndicatorsApiResponse {
  symbol: string;
  tf: string;
  overlays: ChartOverlays;
  panes: ChartPanes;
  latest_indicators: IndicatorResultItem[];
  calc_time_ms: number;
}

interface AnalisaPageProps {
  symbol: string;
  onSelectSymbol: (symbol: string) => void;
}

const CATEGORY_META: Record<string, { label: string; icon: React.ReactNode }> = {
  trend: { label: "Trend", icon: <TrendingUp className="w-3.5 h-3.5 text-accent" /> },
  momentum: { label: "Momentum", icon: <Gauge className="w-3.5 h-3.5 text-indigo-400" /> },
  order_flow: { label: "Order Flow", icon: <Waves className="w-3.5 h-3.5 text-teal-400" /> },
  derivatives: { label: "Derivatif", icon: <Layers className="w-3.5 h-3.5 text-amber-400" /> },
  microstructure: { label: "Mikrostruktur", icon: <BookOpen className="w-3.5 h-3.5 text-sky-400" /> },
  ml: { label: "Machine Learning", icon: <Brain className="w-3.5 h-3.5 text-purple-400" /> },
  sentiment: { label: "Sentimen", icon: <Smile className="w-3.5 h-3.5 text-pink-400" /> },
};

const INDICATOR_NAMES: Record<string, string> = {
  vwap: "VWAP & Bands",
  ema_ribbon: "EMA Ribbon (8..55)",
  supertrend: "Supertrend (ATR 10, 3.0)",
  rsi_div: "RSI Divergence (14)",
  bollinger: "Bollinger Bands & Squeeze",
  cvd_obv: "CVD / OBV Slope",
  funding_oi: "Funding Rate & Open Interest",
  orderbook: "Order Book Imbalance (OBI)",
  lightgbm: "LightGBM Direction ML",
  sentiment: "Fear & Greed / LS Ratio",
};

export const AnalisaPage: React.FC<AnalisaPageProps> = ({
  symbol,
  onSelectSymbol,
}) => {
  const { ticks, latestCandle, symbols, goldSourceAlert, wsConnected, subscribe } = useMarket();
  const [selectedTf, setSelectedTf] = useState<string>("M15");
  const [candles, setCandles] = useState<ChartCandle[]>([]);
  const [indicatorsData, setIndicatorsData] = useState<IndicatorsApiResponse | null>(null);
  const [analysisData, setAnalysisData] = useState<AnalysisResponse | null>(null);
  const [scoreHistory, setScoreHistory] = useState<ScorePoint[]>([]);
  const [signalMarkers, setSignalMarkers] = useState<SignalChartMarker[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [lastTickPrice, setLastTickPrice] = useState<number | null>(null);
  const [activeTicket, setActiveTicket] = useState<TicketItem | null>(null);
  const [priceFlash, setPriceFlash] = useState<"up" | "down" | null>(null);

  // Overlay and Pane Toggles
  const [activeOverlays, setActiveOverlays] = useState({
    vwap: true,
    ema_ribbon: false,
    supertrend: true,
    bollinger: false,
  });

  const [activePanes, setActivePanes] = useState({
    rsi: true,
    cvd: false,
  });

  const prevPriceRef = useRef<number | null>(null);

  // Normalize symbol query
  const querySymbol = symbol === "XAUUSDT" ? "XAUUSD" : symbol;
  const currentSymbolMeta = symbols.find(
    (s) => s.symbol === querySymbol || s.symbol === symbol
  );

  const isGold = querySymbol === "XAUUSD" || symbol === "XAUUSDT";
  const isFallback = Boolean(
    isGold && (currentSymbolMeta?.is_fallback || goldSourceAlert?.active.includes("PAXG"))
  );

  const timeframes = ["M15", "H1", "H4", "D1"];

  // Fetch initial candles
  const fetchCandles = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await apiClient.GET("/api/candles", {
        params: {
          query: {
            symbol: querySymbol,
            tf: selectedTf,
            limit: 300,
          },
        },
      });

      if (res.data) {
        const rawList = res.data as CandleItem[];
        const formatted: ChartCandle[] = rawList.map((c) => ({
          open_time: c.open_time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume,
          is_closed: c.is_closed,
        }));
        setCandles(formatted);
      }
    } catch (err) {
      console.error("Gagal memuat candles:", err);
    } finally {
      setIsLoading(false);
    }
  }, [querySymbol, selectedTf]);

  // Fetch overlays and panes
  const fetchIndicators = useCallback(async () => {
    try {
      const res = await apiClient.GET("/api/indicators", {
        params: {
          query: {
            symbol: querySymbol,
            tf: selectedTf,
            limit: 300,
          },
        },
      });

      if (res.data) {
        setIndicatorsData(res.data as IndicatorsApiResponse);
      }
    } catch (err) {
      console.error("Gagal memuat chart overlays:", err);
    }
  }, [querySymbol, selectedTf]);

  // Fetch full analysis & macro filters
  const fetchAnalysis = useCallback(async () => {
    try {
      const res = await apiClient.GET("/api/analysis/{symbol}", {
        params: {
          path: { symbol: querySymbol },
          query: { tf: selectedTf },
        },
      });

      if (res.data) {
        setAnalysisData(res.data as AnalysisResponse);
      }
    } catch (err) {
      console.error("Gagal memuat analisa konfluensi:", err);
    }
  }, [querySymbol, selectedTf]);

  // Fetch score history for area chart
  const fetchScoreHistory = useCallback(async () => {
    try {
      const res = await apiClient.GET("/api/analysis/{symbol}/history", {
        params: {
          path: { symbol: querySymbol },
          query: { tf: selectedTf, limit: 48 },
        },
      });

      if (res.data?.history) {
        setScoreHistory(res.data.history as ScorePoint[]);
      }
    } catch (err) {
      console.error("Gagal memuat riwayat skor:", err);
    }
  }, [querySymbol, selectedTf]);

  // Fetch historical signal markers for chart
  const fetchSignals = useCallback(async () => {
    try {
      const res = await apiClient.GET("/api/signals", {
        params: {
          query: { symbol: querySymbol, limit: 40 },
        },
      });

      if (res.data?.signals) {
        const sigs = (res.data as SignalsResponse).signals;
        const markers: SignalChartMarker[] = sigs.map((s) => {
          const t = Math.floor(new Date(s.bar_time).getTime() / 1000) as UTCTimestamp;
          const isBuy = s.side === "LONG";
          return {
            time: t,
            position: isBuy ? "belowBar" : "aboveBar",
            color: isBuy ? "#22C55E" : "#EF4444",
            shape: isBuy ? "arrowUp" : "arrowDown",
            text: `${s.verdict} (${s.strategy})`,
          };
        });
        setSignalMarkers(markers);
      }
    } catch (err) {
      console.error("Gagal memuat sinyal marker:", err);
    }
  }, [querySymbol]);

  // Fetch active ticket for this symbol
  const fetchTicket = useCallback(async () => {
    try {
      const res = await apiClient.GET("/api/tickets", {
        params: {
          query: {
            symbol: querySymbol,
            status: "new",
            limit: 1,
          },
        },
      });
      if (res.data && Array.isArray(res.data) && res.data.length > 0) {
        setActiveTicket(res.data[0] as TicketItem);
      } else {
        setActiveTicket(null);
      }
    } catch (err) {
      console.error("Gagal memuat trade ticket:", err);
    }
  }, [querySymbol]);

  useEffect(() => {
    fetchCandles();
    fetchIndicators();
    fetchAnalysis();
    fetchScoreHistory();
    fetchSignals();
    fetchTicket();
    subscribe([querySymbol, symbol], [selectedTf]);
  }, [
    fetchCandles,
    fetchIndicators,
    fetchAnalysis,
    fetchScoreHistory,
    fetchSignals,
    fetchTicket,
    querySymbol,
    symbol,
    selectedTf,
    subscribe,
  ]);

  // Tick flash detection
  const liveTick = ticks[querySymbol] || ticks[symbol];
  useEffect(() => {
    if (liveTick?.price) {
      const curPrice = liveTick.price;
      if (prevPriceRef.current !== null && prevPriceRef.current !== curPrice) {
        setPriceFlash(curPrice > prevPriceRef.current ? "up" : "down");
        const timer = setTimeout(() => setPriceFlash(null), 800);
        prevPriceRef.current = curPrice;
        setLastTickPrice(curPrice);
        return () => clearTimeout(timer);
      }
      prevPriceRef.current = curPrice;
      setLastTickPrice(curPrice);
    }
  }, [liveTick]);

  // Merge live running bar from websocket
  const liveBarKey = `${querySymbol}:${selectedTf}`;
  const liveBar = latestCandle[liveBarKey];

  const handleToggleOverlay = (key: "vwap" | "ema_ribbon" | "supertrend" | "bollinger") => {
    setActiveOverlays((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleTogglePane = (key: "rsi" | "cvd") => {
    setActivePanes((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="space-y-4">
      {/* Fallback Banner for Gold */}
      {isFallback && (
        <div
          role="alert"
          className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-500 flex items-start gap-3 shadow-sm animate-pulse"
        >
          <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5 text-amber-500" />
          <div className="text-sm">
            <h4 className="font-semibold text-amber-500">
              Perhatian Sumber Data: Mode Cadangan PAXGUSDT Aktif
            </h4>
            <p className="mt-0.5 text-xs text-amber-500/90 leading-relaxed">
              Koneksi ke data Binance Futures XAUUSDT terputus/terkendala (
              {goldSourceAlert?.reason || "Timeout > 120s"}). Sistem secara otomatis beralih
              menggunakan Binance Spot PAXGUSDT demi menjaga kontinuitas analisis.
            </p>
          </div>
        </div>
      )}

      {/* Top Controls Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-surface p-4 rounded-xl border border-border shadow-sm">
        {/* Left: Symbol & Live Price */}
        <div className="flex items-center gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold font-mono tracking-tight text-fg">
                {currentSymbolMeta?.display || symbol}
              </h2>
              <span className="px-2 py-0.5 text-[11px] font-semibold uppercase rounded-full bg-surface-2 border border-border text-muted">
                {currentSymbolMeta?.asset || (isGold ? "Gold" : "Crypto")}
              </span>
              <span className="px-2 py-0.5 text-[11px] font-mono rounded bg-accent/10 border border-accent/20 text-accent font-medium">
                {currentSymbolMeta?.active_source || (isFallback ? "binance_spot:PAXGUSDT" : "binance_futures")}
              </span>
            </div>
            <p className="text-xs text-muted mt-0.5">
              10 Indikator Konfluensi, Macro Filter & Strategi Multi-TF
            </p>
          </div>

          {/* Live Price Display */}
          <div className="pl-4 border-l border-border">
            <div className="text-xs text-muted font-medium">Harga Live</div>
            <div
              className={`text-2xl font-bold font-mono transition-colors duration-300 ${
                priceFlash === "up"
                  ? "text-emerald-500 scale-105"
                  : priceFlash === "down"
                  ? "text-rose-500 scale-105"
                  : "text-fg"
              }`}
            >
              {lastTickPrice !== null
                ? lastTickPrice.toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })
                : "—"}
            </div>
          </div>
        </div>

        {/* Right: Symbol Quick-Select & Timeframe Selector & Actions */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center bg-surface-2 p-1 rounded-lg border border-border">
            {symbols.map((s) => {
              const active = s.symbol === querySymbol || s.symbol === symbol;
              return (
                <button
                  key={s.symbol}
                  type="button"
                  onClick={() => onSelectSymbol(s.symbol)}
                  className={`px-2.5 py-1 text-xs font-mono font-semibold rounded transition-colors ${
                    active
                      ? "bg-surface text-accent shadow-sm font-bold"
                      : "text-muted hover:text-fg hover:bg-surface/50"
                  }`}
                >
                  {s.display}
                </button>
              );
            })}
          </div>

          <div className="flex items-center bg-surface-2 p-1 rounded-lg border border-border">
            {timeframes.map((tf) => {
              const active = selectedTf === tf;
              return (
                <button
                  key={tf}
                  type="button"
                  onClick={() => setSelectedTf(tf)}
                  className={`px-3 py-1 text-xs font-mono font-semibold rounded transition-colors ${
                    active
                      ? "bg-accent text-accent-fg shadow-sm font-bold"
                      : "text-muted hover:text-fg hover:bg-surface"
                  }`}
                >
                  {tf}
                </button>
              );
            })}
          </div>

          <button
            type="button"
            onClick={() => {
              fetchCandles();
              fetchIndicators();
              fetchAnalysis();
              fetchScoreHistory();
              fetchSignals();
            }}
            disabled={isLoading}
            className="p-2 rounded-lg bg-surface-2 border border-border text-muted hover:text-fg hover:bg-surface transition-colors"
            title="Muat ulang chart & indikator"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Main Professional 3-Column Trading Terminal Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Column 1: Chart & Score History (Desktop col-span-7) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="w-full">
            {isLoading && candles.length === 0 ? (
              <div className="w-full h-[520px] bg-surface rounded-xl border border-border flex flex-col items-center justify-center text-muted">
                <RefreshCw className="w-8 h-8 animate-spin text-accent mb-2" />
                <span className="text-sm font-semibold">Memuat data market & indikator...</span>
              </div>
            ) : (
              <TradingViewChart
                candles={candles}
                liveCandle={liveBar || null}
                symbol={currentSymbolMeta?.display || symbol}
                tf={selectedTf}
                overlays={indicatorsData?.overlays}
                panes={indicatorsData?.panes}
                markers={signalMarkers}
                activeOverlays={activeOverlays}
                activePanes={activePanes}
                onToggleOverlay={handleToggleOverlay}
                onTogglePane={handleTogglePane}
              />
            )}
          </div>

          {/* 48-Hour Score History Mini Area Chart */}
          <ScoreHistoryChart history={scoreHistory} />
        </div>

        {/* Column 2: 10 Indicators & Gauge (Desktop col-span-5 xl:col-span-5) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Confluence Score Gauge */}
          {analysisData ? (
            <ScoreGauge
              score={analysisData.score}
              verdict={analysisData.verdict}
              counts={analysisData.counts}
            />
          ) : (
            <div className="p-6 rounded-xl bg-surface border border-border text-center text-muted text-sm">
              Menghitung skor konfluensi...
            </div>
          )}

          {/* 10 Categorized Indicator Cards */}
          <div className="p-4 rounded-xl bg-surface border border-border shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-accent" />
                <h3 className="text-sm font-bold text-fg tracking-wide">
                  Detail 10 Indikator Konfluensi
                </h3>
              </div>
              <span className="text-xs text-muted font-mono">
                {selectedTf} Close
              </span>
            </div>

            {/* List of 10 Indicator Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {(analysisData?.indicators || indicatorsData?.latest_indicators || []).map((ind) => {
                const catInfo = CATEGORY_META[ind.category] || {
                  label: ind.category,
                  icon: <Activity className="w-3.5 h-3.5 text-accent" />,
                };
                const indName = INDICATOR_NAMES[ind.key] || ind.key;
                const isBull = ind.state === "BULL";
                const isBear = ind.state === "BEAR";
                const isNeutral = ind.state === "NEUTRAL";
                const isNA = ind.state === "NA";

                const badgeColor = isBull
                  ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400"
                  : isBear
                  ? "bg-rose-500/15 border-rose-500/30 text-rose-400"
                  : isNeutral
                  ? "bg-amber-500/10 border-amber-500/20 text-amber-500"
                  : "bg-surface-2 border-border text-muted/60";

                const strengthPct = Math.round(ind.strength * 100);

                return (
                  <div
                    key={ind.key}
                    className={`p-3 rounded-lg border transition-colors flex flex-col justify-between ${
                      isNA
                        ? "bg-surface-2/20 border-border/40 opacity-60"
                        : "bg-surface-2/40 border-border hover:border-accent/40"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-1 mb-1">
                      <div>
                        <div className="font-semibold text-xs text-fg flex items-center gap-1.5">
                          {catInfo.icon}
                          <span>{indName}</span>
                        </div>
                        <div className="text-[10px] text-muted font-mono">{catInfo.label}</div>
                      </div>
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold font-mono border ${badgeColor}`}
                      >
                        {ind.state}
                      </span>
                    </div>

                    {/* Strength Bar */}
                    {!isNA && (
                      <div className="space-y-1 my-1.5">
                        <div className="flex items-center justify-between text-[10px] font-mono text-muted">
                          <span>Kekuatan</span>
                          <strong className="text-fg">{strengthPct}%</strong>
                        </div>
                        <div className="w-full h-1 bg-surface rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-300 ${
                              isBull
                                ? "bg-emerald-500"
                                : isBear
                                ? "bg-rose-500"
                                : "bg-amber-500"
                            }`}
                            style={{ width: `${Math.max(strengthPct, 6)}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {/* Indonesian reason */}
                    <p className="text-[11px] text-muted leading-tight mt-1">
                      {ind.reason}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Decision Row: Macro Filter, HTF Biases, Strategy B, Ticket Teaser */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* 1. Macro Filter Checklist (M1-M8) */}
        {analysisData?.macro && (
          <MacroChecklist
            passed={analysisData.macro.passed}
            checks={analysisData.macro.checks as MacroCheckItem[]}
            blockedBy={analysisData.macro.blocked_by}
          />
        )}

        {/* 2. HTF Trend Biases & Strategy B */}
        <div className="space-y-4">
          {/* HTF Multi-Timeframe Bias Card */}
          <div className="p-4 rounded-xl bg-surface border border-border shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-accent" />
                <h3 className="text-sm font-bold text-fg tracking-wide">
                  Bias Multi-Timeframe (HTF)
                </h3>
              </div>
              <span className="text-xs text-muted font-mono">Tren Besar</span>
            </div>

            <div className="grid grid-cols-3 gap-2 text-center font-mono">
              <div className="p-2.5 rounded-lg bg-surface-2/40 border border-border">
                <div className="text-[10px] text-muted uppercase">H1 Konfirmasi</div>
                <div
                  className={`text-sm font-bold mt-1 ${
                    analysisData?.htf.H1 === "BULL"
                      ? "text-emerald-400"
                      : analysisData?.htf.H1 === "BEAR"
                      ? "text-rose-400"
                      : "text-muted"
                  }`}
                >
                  {analysisData?.htf.H1 || "—"}
                </div>
              </div>
              <div className="p-2.5 rounded-lg bg-surface-2/40 border border-border">
                <div className="text-[10px] text-muted uppercase">H4 EMA200</div>
                <div
                  className={`text-sm font-bold mt-1 ${
                    analysisData?.htf.H4 === "BULL"
                      ? "text-emerald-400"
                      : analysisData?.htf.H4 === "BEAR"
                      ? "text-rose-400"
                      : "text-muted"
                  }`}
                >
                  {analysisData?.htf.H4 || "—"}
                </div>
              </div>
              <div className="p-2.5 rounded-lg bg-surface-2/40 border border-border">
                <div className="text-[10px] text-muted uppercase">D1 Supertrend</div>
                <div
                  className={`text-sm font-bold mt-1 ${
                    analysisData?.htf.D1 === "BULL"
                      ? "text-emerald-400"
                      : analysisData?.htf.D1 === "BEAR"
                      ? "text-rose-400"
                      : "text-muted"
                  }`}
                >
                  {analysisData?.htf.D1 || "—"}
                </div>
              </div>
            </div>
          </div>

          {/* Strategy B Panel */}
          {analysisData?.strategy_b && (
            <StrategyBPanel data={analysisData.strategy_b as StrategyBData} />
          )}
        </div>

        {/* 3. Trade Ticket & AI Commentary Cards */}
        <div className="space-y-4">
          {activeTicket ? (
            <TicketCard
              ticket={activeTicket}
              onRefresh={() => {
                fetchTicket();
                fetchAnalysis();
              }}
            />
          ) : (
            <div className="p-4 rounded-xl bg-surface border border-border shadow-sm space-y-3">
              <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
                <div className="flex items-center gap-2">
                  <Zap className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-sm font-bold text-fg tracking-wide">
                    Trade Ticket (Eksekusi Manual)
                  </h3>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-muted/20 border border-border text-muted font-mono">
                  Siaga
                </span>
              </div>

              {analysisData?.verdict.includes("STRONG") ? (
                <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-xs text-fg space-y-2">
                  <div className="flex items-center justify-between font-bold">
                    <span className="text-emerald-400">
                      🟢 SINYAL AKTIF: {analysisData.verdict}
                    </span>
                    <span className="font-mono text-muted">Skor: {analysisData.score}</span>
                  </div>
                  <p className="text-[11px] text-muted leading-tight">
                    Sinyal konfluensi kuat terkonfirmasi dan lolos Macro Filter.
                  </p>
                </div>
              ) : (
                <div className="p-3 rounded-lg bg-surface-2/40 text-xs text-muted leading-relaxed">
                  Trade Ticket dihasilkan otomatis saat skor konfluensi mencapai ambang <strong>STRONG BUY</strong> (≥ 55) atau <strong>STRONG SELL</strong> (≤ -55) dan lolos semua filter macro.
                </div>
              )}
            </div>
          )}

          {/* AI Commentary Panel */}
          <AICommentPanel symbol={symbol} tf={selectedTf} />
        </div>
      </div>

      {/* Footer Status Bar */}
      <div className="flex flex-wrap items-center justify-between text-xs text-muted px-2 py-1">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                wsConnected ? "bg-emerald-500 animate-pulse" : "bg-rose-500"
              }`}
            />
            <span>WebSocket {wsConnected ? "Tersambung (Real-time)" : "Terputus"}</span>
          </div>
          <div className="hidden sm:flex items-center gap-1.5 text-muted/80">
            <Activity className="w-3.5 h-3.5 text-accent" />
            <span>Kalkulasi 10 Indikator Inkremental & Macro Filter Aktif</span>
          </div>
        </div>

        {isGold && currentSymbolMeta?.gold_status && (
          <div className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-accent" />
            <span>
              Sesi Pasar Gold:{" "}
              <strong className="text-fg">
                {currentSymbolMeta.gold_status.is_open ? "BUKA" : "TUTUP"}
              </strong>
              {currentSymbolMeta.gold_status.reason && (
                <span className="ml-1 text-amber-500/90">
                  ({currentSymbolMeta.gold_status.reason})
                </span>
              )}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
