import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { JurnalPage } from "./JurnalPage";
import { api, type JournalResponse, type TradeAnalysisSnapshotResponse } from "../api/client";

const mockJournalResponse: JournalResponse = {
  book: "paper",
  filter_symbol: null,
  filter_strategy: null,
  kpis: {
    total_trades: 12,
    wins: 8,
    losses: 3,
    breakevens: 1,
    winrate_pct: 66.7,
    profit_factor: 2.45,
    expectancy_r: 0.65,
    avg_win_r: 1.5,
    avg_loss_r: -0.9,
    max_drawdown_pct: 4.2,
    max_drawdown_r: 1.8,
    max_drawdown_usd: 180.0,
    current_streak: 2,
    max_win_streak: 4,
    max_loss_streak: 2,
    total_realized_pnl_usd: 650.0,
    total_realized_pnl_r: 6.5,
  },
  compare_kpis: null,
  equity_curve: [
    {
      trade_number: 1,
      timestamp: "2026-10-15T10:00:00Z",
      equity_r: 1.5,
      equity_usd: 150.0,
      drawdown_r: 0.0,
      drawdown_pct: 0.0,
    },
    {
      trade_number: 2,
      timestamp: "2026-10-15T12:00:00Z",
      equity_r: 3.0,
      equity_usd: 300.0,
      drawdown_r: 0.0,
      drawdown_pct: 0.0,
    },
  ],
  compare_equity_curve: null,
  heatmap: [
    {
      day_of_week: 0,
      hour_of_day: 14,
      total_trades: 2,
      wins: 2,
      losses: 0,
      winrate_pct: 100.0,
      net_r: 2.5,
      net_pnl_usd: 250.0,
    },
  ],
  breakdowns: {
    symbol: [
      {
        category: "BTCUSDT",
        trades: 7,
        wins: 5,
        losses: 2,
        breakevens: 0,
        winrate_pct: 71.4,
        total_r: 4.5,
        total_pnl_usd: 450.0,
        profit_factor: 2.8,
        expectancy_r: 0.64,
      },
      {
        category: "XAUUSD",
        trades: 5,
        wins: 3,
        losses: 1,
        breakevens: 1,
        winrate_pct: 60.0,
        total_r: 2.0,
        total_pnl_usd: 200.0,
        profit_factor: 2.1,
        expectancy_r: 0.4,
      },
    ],
    strategy: [
      {
        category: "konfluensi10",
        trades: 12,
        wins: 8,
        losses: 3,
        breakevens: 1,
        winrate_pct: 66.7,
        total_r: 6.5,
        total_pnl_usd: 650.0,
        profit_factor: 2.45,
        expectancy_r: 0.65,
      },
    ],
    session: [],
    verdict: [],
  },
  indicator_accuracy: [
    {
      indicator_name: "EMA Trend 200",
      aligned_trades: 8,
      aligned_wins: 6,
      aligned_winrate_pct: 75.0,
      aligned_r_contrib: 5.0,
      contrarian_trades: 4,
      contrarian_wins: 2,
      contrarian_winrate_pct: 50.0,
      contrarian_r_contrib: 1.5,
    },
    {
      indicator_name: "RSI 14 Zone",
      aligned_trades: 9,
      aligned_wins: 7,
      aligned_winrate_pct: 77.8,
      aligned_r_contrib: 5.5,
      contrarian_trades: 3,
      contrarian_wins: 1,
      contrarian_winrate_pct: 33.3,
      contrarian_r_contrib: 1.0,
    },
  ],
  macro_filter_impact: [
    {
      rule_code: "M1",
      rule_name: "Spread / Session Filter",
      blocked_count: 5,
      virtual_wins_missed: 1,
      virtual_losses_prevented: 4,
      net_r_saved: 2.5,
    },
    {
      rule_code: "M2",
      rule_name: "Red News Blackout",
      blocked_count: 3,
      virtual_wins_missed: 0,
      virtual_losses_prevented: 3,
      net_r_saved: 3.0,
    },
  ],
  slippage_metrics: {
    total_real_trades: 5,
    avg_slippage_points: 0.35,
    max_slippage_points: 0.8,
    total_slippage_cost_usd: 35.0,
    breakdown_by_broker: {
      ICMarkets: { count: 3, avg_points: 0.3, cost_usd: 20.0 },
      BinanceFutures: { count: 2, avg_points: 0.4, cost_usd: 15.0 },
    },
    breakdown_by_symbol: {
      XAUUSD: { count: 3, avg_points: 0.3, cost_usd: 20.0 },
      BTCUSDT: { count: 2, avg_points: 0.4, cost_usd: 15.0 },
    },
  },
  trades: [
    {
      id: "pt-1",
      book: "paper",
      symbol: "BTCUSDT",
      side: "LONG",
      strategy: "konfluensi10",
      entry_price: 81000.0,
      exit_price: 82500.0,
      lot: 0.05,
      entry_time: "2026-10-15T10:00:00Z",
      exit_time: "2026-10-15T11:30:00Z",
      outcome: "WIN",
      exit_reason: "TP1",
      pnl_usd: 150.0,
      pnl_r: 1.5,
      analysis_id: 101,
      slippage_points: null,
    },
    {
      id: "pt-2",
      book: "paper",
      symbol: "XAUUSD",
      side: "SHORT",
      strategy: "konfluensi10",
      entry_price: 2650.0,
      exit_price: 2640.0,
      lot: 0.1,
      entry_time: "2026-10-15T12:00:00Z",
      exit_time: "2026-10-15T13:45:00Z",
      outcome: "WIN",
      exit_reason: "TP2",
      pnl_usd: 150.0,
      pnl_r: 1.5,
      analysis_id: 102,
      slippage_points: null,
    },
  ],
};

const mockSnapshotResponse: TradeAnalysisSnapshotResponse = {
  trade: {
    id: "pt-1",
    book: "paper",
    symbol: "BTCUSDT",
    side: "LONG",
    strategy: "konfluensi10",
    entry_price: 81000.0,
    exit_price: 82500.0,
    lot: 0.05,
    entry_time: "2026-10-15T10:00:00Z",
    exit_time: "2026-10-15T11:30:00Z",
    outcome: "WIN",
    exit_reason: "TP1",
    pnl_usd: 150.0,
    pnl_r: 1.5,
    analysis_id: 101,
  },
  analysis: {
    symbol: "BTCUSDT",
    timeframe: "M15",
    timestamp: "2026-10-15T10:00:00Z",
    score: 75.0,
    verdict: "KUAT_BELI",
    strategy: "konfluensi10",
    weights_version: "v1.0",
    indicators: {
      ema_trend: { state: "BULLISH", value: 80500.0 },
      rsi_14: { state: "BULLISH", value: 58.2 },
    },
    macro_checks: {
      M1: { passed: true },
      M2: { passed: true },
    },
    ai_comment: {
      text: "Konfluensi bullish kuat didorong EMA dan RSI sehat.",
    },
  },
};

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
      expect(screen.getByText("-4,2%")).toBeInTheDocument();
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
      expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
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
      expect(screen.getByText("Konfluensi bullish kuat didorong EMA dan RSI sehat.")).toBeInTheDocument();
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
