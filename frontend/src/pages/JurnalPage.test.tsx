import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { JurnalPage } from "./JurnalPage";
import {
  api,
  type JournalResponse,
  type TradeAnalysisSnapshotResponse,
} from "../api/client";

const mockJournalResponse: JournalResponse = {
  book: "paper",
  filter_range: "all",
  filter_symbol: null,
  filter_strategy: null,
  kpis: {
    total_trades: 12,
    win_trades: 8,
    loss_trades: 3,
    be_trades: 1,
    winrate_pct: 66.7,
    profit_factor: 2.45,
    expectancy_r: 0.65,
    avg_win_r: 1.5,
    avg_loss_r: -0.9,
    risk_reward_ratio: 1.67,
    max_drawdown_r: 1.8,
    max_drawdown_usd: 180.0,
    current_streak: 2,
    max_win_streak: 4,
    max_loss_streak: 2,
    total_pnl_usd: 650.0,
    total_pnl_r: 6.5,
    gross_profit_usd: 1000.0,
    gross_loss_usd: 350.0,
  },
  compare_paper_kpis: null,
  compare_real_kpis: null,
  equity_curve: [
    {
      trade_id: 1,
      time: "2026-10-15T10:00:00Z",
      time_wib: "15 Okt 17:00",
      symbol: "BTCUSDT",
      side: "LONG",
      pnl_r: 1.5,
      pnl_usd: 150.0,
      cumulative_r: 1.5,
      cumulative_usd: 150.0,
      drawdown_r: 0.0,
    },
    {
      trade_id: 2,
      time: "2026-10-15T12:00:00Z",
      time_wib: "15 Okt 19:00",
      symbol: "XAUUSD",
      side: "SHORT",
      pnl_r: 1.5,
      pnl_usd: 150.0,
      cumulative_r: 3.0,
      cumulative_usd: 300.0,
      drawdown_r: 0.0,
    },
  ],
  heatmap: [
    {
      day_of_week: 0,
      day_name: "Senin",
      hour_wib: 14,
      total_trades: 2,
      win_trades: 2,
      winrate_pct: 100.0,
      total_pnl_r: 2.5,
      total_pnl_usd: 250.0,
    },
  ],
  breakdowns: {
    symbol: [
      {
        category: "BTCUSDT",
        total_trades: 7,
        win_trades: 5,
        loss_trades: 2,
        winrate_pct: 71.4,
        total_pnl_r: 4.5,
        total_pnl_usd: 450.0,
        profit_factor: 2.8,
        expectancy_r: 0.64,
        avg_win_r: 1.5,
        avg_loss_r: -0.9,
      },
      {
        category: "XAUUSD",
        total_trades: 5,
        win_trades: 3,
        loss_trades: 1,
        winrate_pct: 60.0,
        total_pnl_r: 2.0,
        total_pnl_usd: 200.0,
        profit_factor: 2.1,
        expectancy_r: 0.4,
        avg_win_r: 1.4,
        avg_loss_r: -1.0,
      },
    ],
    strategy: [
      {
        category: "konfluensi10",
        total_trades: 12,
        win_trades: 8,
        loss_trades: 3,
        winrate_pct: 66.7,
        total_pnl_r: 6.5,
        total_pnl_usd: 650.0,
        profit_factor: 2.45,
        expectancy_r: 0.65,
        avg_win_r: 1.5,
        avg_loss_r: -0.9,
      },
    ],
    session: [],
    verdict: [],
  },
  indicator_accuracy: [
    {
      name: "EMA Trend 200",
      aligned_trades: 8,
      aligned_wins: 6,
      aligned_winrate_pct: 75.0,
      aligned_avg_r: 1.25,
      contrarian_trades: 4,
      contrarian_wins: 2,
      contrarian_winrate_pct: 50.0,
      contrarian_avg_r: 0.38,
      net_edge_pct: 25.0,
    },
    {
      name: "RSI 14 Zone",
      aligned_trades: 9,
      aligned_wins: 7,
      aligned_winrate_pct: 77.8,
      aligned_avg_r: 1.3,
      contrarian_trades: 3,
      contrarian_wins: 1,
      contrarian_winrate_pct: 33.3,
      contrarian_avg_r: 0.33,
      net_edge_pct: 44.5,
    },
  ],
  macro_filter_impact: [
    {
      code: "M1",
      name: "Spread / Session Filter",
      blocked_count: 5,
      virtual_wins_missed: 1,
      virtual_losses_prevented: 4,
      net_r_saved: 2.5,
      effectiveness: "Sangat Efektif",
    },
    {
      code: "M2",
      name: "Red News Blackout",
      blocked_count: 3,
      virtual_wins_missed: 0,
      virtual_losses_prevented: 3,
      net_r_saved: 3.0,
      effectiveness: "Sangat Efektif",
    },
  ],
  slippage_metrics: {
    total_executions: 5,
    avg_slippage_points: 0.35,
    median_slippage_points: 0.3,
    min_slippage_points: 0.1,
    max_slippage_points: 0.8,
    total_slippage_cost_usd: 35.0,
    by_broker: [
      {
        broker_profile: "ICMarkets",
        total_executions: 3,
        avg_slippage_points: 0.3,
        total_slippage_cost_usd: 20.0,
      },
      {
        broker_profile: "BinanceFutures",
        total_executions: 2,
        avg_slippage_points: 0.4,
        total_slippage_cost_usd: 15.0,
      },
    ],
    by_symbol: [
      {
        symbol: "XAUUSD",
        total_executions: 3,
        avg_slippage_points: 0.3,
        total_slippage_cost_usd: 20.0,
      },
      {
        symbol: "BTCUSDT",
        total_executions: 2,
        avg_slippage_points: 0.4,
        total_slippage_cost_usd: 15.0,
      },
    ],
  },
  trades: [
    {
      id: 1,
      ticket_id: 10,
      book: "paper",
      symbol: "BTCUSDT",
      side: "LONG",
      strategy: "konfluensi10",
      entry_price: 81000.0,
      exit_price: 82500.0,
      entry_time: "2026-10-15T10:00:00Z",
      entry_time_wib: "15 Okt 17:00",
      exit_time: "2026-10-15T11:30:00Z",
      exit_time_wib: "15 Okt 18:30",
      exit_reason: "TP1",
      bars_held: 6,
      pnl_usd: 150.0,
      pnl_r: 1.5,
      analysis_id: 101,
      fees_usd: 1.5,
      verdict: "KUAT_BELI",
      session: "Asia",
      slippage_points: 0.0,
      is_virtual: false,
    },
    {
      id: 2,
      ticket_id: 11,
      book: "paper",
      symbol: "XAUUSD",
      side: "SHORT",
      strategy: "konfluensi10",
      entry_price: 2650.0,
      exit_price: 2640.0,
      entry_time: "2026-10-15T12:00:00Z",
      entry_time_wib: "15 Okt 19:00",
      exit_time: "2026-10-15T13:45:00Z",
      exit_time_wib: "15 Okt 20:45",
      exit_reason: "TP2",
      bars_held: 7,
      pnl_usd: 150.0,
      pnl_r: 1.5,
      analysis_id: 102,
      fees_usd: 2.0,
      verdict: "KUAT_JUAL",
      session: "London",
      slippage_points: 0.0,
      is_virtual: false,
    },
  ],
};

const mockSnapshotResponse = {
  trade_id: 1,
  symbol: "BTCUSDT",
  tf: "M15",
  bar_time: "2026-10-15T10:00:00Z",
  score: 75.0,
  verdict: "KUAT_BELI",
  weights_version: "v1.0",
  indicators: [
    {
      key: "ema_trend",
      name: "EMA Trend 200",
      category: "trend",
      state: "BULL",
      strength: 1.0,
      reason: "Harga di atas EMA 200",
      live_only: false,
    },
    {
      key: "rsi_14",
      name: "RSI 14",
      category: "momentum",
      state: "BULL",
      strength: 1.0,
      reason: "RSI 58 zona momentum",
      live_only: false,
    },
  ],
  counts: {},
  category_votes: {},
  macro: {
    M1: { passed: true },
    M2: { passed: true },
  },
  htf: {
    H1: "BULLISH",
    H4: "BULLISH",
  },
  strategy_b: {},
} as unknown as TradeAnalysisSnapshotResponse;

describe("JurnalPage Component", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders journal KPIs and analytical widgets", async () => {
    vi.spyOn(api, "getJournalStats").mockResolvedValue(mockJournalResponse);

    render(<JurnalPage />);

    // Check main title
    await waitFor(() => {
      expect(screen.getByText("Jurnal & Statistik Winrate")).toBeInTheDocument();
      // Check KPI values
      expect(screen.getByText("66,7%")).toBeInTheDocument();
      expect(screen.getByText("2,45")).toBeInTheDocument();
      expect(screen.getByText("+0,65 R")).toBeInTheDocument();
      expect(screen.getByText("+$650,00")).toBeInTheDocument();
      expect(screen.getByText("-1,8 R")).toBeInTheDocument();
    });

    // Check charts and cards titles
    expect(screen.getByText("Kurva Ekuitas Kumulatif")).toBeInTheDocument();
    expect(screen.getByText("Distribusi Hasil (R-Multiple)")).toBeInTheDocument();
    expect(screen.getByText("Heatmap Jam & Hari (WIB)")).toBeInTheDocument();
    expect(screen.getByText("Breakdown Multidimensi")).toBeInTheDocument();
    expect(screen.getByText("Akurasi per Indikator")).toBeInTheDocument();
    expect(screen.getByText("Nilai & Efektivitas Macro Filter (M1–M8)")).toBeInTheDocument();

    // Check trades in table
    expect(screen.getByText("Riwayat Posisi & Eksekusi (2)")).toBeInTheDocument();
    expect(screen.getAllByText("BTCUSDT").length).toBeGreaterThan(0);
  });

  it("opens and displays Trade Analysis Snapshot modal when snapshot eye icon is clicked", async () => {
    vi.spyOn(api, "getJournalStats").mockResolvedValue(mockJournalResponse);
    vi.spyOn(api, "getTradeSnapshot").mockResolvedValue(mockSnapshotResponse);

    render(<JurnalPage />);

    await waitFor(() => {
      expect(screen.getAllByText("BTCUSDT").length).toBeGreaterThan(0);
    });

    // Find and click the snapshot button (first eye button)
    const snapshotBtns = screen.getAllByTitle("Buka Snapshot Analisa Sinyal");
    expect(snapshotBtns.length).toBeGreaterThan(0);
    fireEvent.click(snapshotBtns[0]);

    // Modal should show up
    await waitFor(() => {
      expect(screen.getByText("Snapshot Analisa Sinyal")).toBeInTheDocument();
      expect(screen.getByText("75 / 100")).toBeInTheDocument();
      expect(screen.getByText("KUAT_BELI")).toBeInTheDocument();
      expect(screen.getByText("Konfirmasi Higher Timeframe (H1 / H4 / D1)")).toBeInTheDocument();
    });
  });

  it("handles book toggling between Paper, Real, and Bandingkan", async () => {
    let requestedBook = "paper";
    vi.spyOn(api, "getJournalStats").mockImplementation(async (params) => {
      requestedBook = params.book || "paper";
      return {
        ...mockJournalResponse,
        book: requestedBook,
      };
    });

    render(<JurnalPage />);

    await waitFor(() => {
      expect(screen.getByText("Jurnal & Statistik Winrate")).toBeInTheDocument();
    });

    // Toggle to Real
    const realButton = screen.getByText("Jurnal Real");
    fireEvent.click(realButton);

    await waitFor(() => {
      expect(requestedBook).toBe("real");
    });

    // In Real mode, slippage card should be visible
    await waitFor(() => {
      expect(screen.getByText("Analisis Slippage Eksekusi Nyata")).toBeInTheDocument();
    });
  });
});
