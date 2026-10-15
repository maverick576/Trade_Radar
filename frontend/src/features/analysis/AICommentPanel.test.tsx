import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { AICommentPanel } from "./AICommentPanel";

const mockCommentResponse = {
  symbol: "BTCUSDT",
  tf: "M15",
  provider: "gemini",
  model: "gemini-2.5-flash",
  valid: true,
  is_fallback: false,
  latency_ms: 1850,
  tokens_in: 320,
  tokens_out: 280,
  created_at: "2026-10-15T06:45:00Z",
  analysis_id: 1,
  comment: {
    ringkasan: "Harga Bitcoin berkonsolidasi di atas VWAP dengan momentum RSI bullish.",
    bias: "bullish",
    keyakinan: "tinggi",
    setuju_dengan_engine: true,
    alasan_utama: [
      "Harga bertahan di atas VWAP 81250",
      "EMA Ribbon tersusun rapi pola ekspansi",
    ],
    risiko: ["Funding rate meningkat di pasar derivatif"],
    skenario_bullish: "Breakout level 81800 berpeluang mendorong ke 82500",
    skenario_bearish: "Penembusan ke bawah 80800 membatalkan struktur tren",
    level_penting: [81250.0, 81800.0, 80800.0],
    invalidasi: "Candle M15 close di bawah 80800",
    saran_manajemen: "Gunakan risiko maksimal 1.5% dari modal",
  },
};

const mockQuotaResponse = {
  rpm_used: 1,
  rpm_limit: 5,
  rpm_remaining: 4,
  rpd_used: 12,
  rpd_limit: 100,
  rpd_remaining: 88,
  provider: "gemini",
  model: "gemini-2.5-flash",
};

describe("AICommentPanel Component", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders structured AI comment content properly", async () => {
    global.fetch = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : "url" in input ? input.url : String(input);
      if (url.includes("/api/analysis/BTCUSDT/ai")) {
        return Promise.resolve(
          new Response(JSON.stringify(mockCommentResponse), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      }
      if (url.includes("/api/ai/quota")) {
        return Promise.resolve(
          new Response(JSON.stringify(mockQuotaResponse), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });

    render(<AICommentPanel symbol="BTCUSDT" tf="M15" />);

    await waitFor(() => {
      expect(screen.getByText("Tanggapan AI")).toBeInTheDocument();
      expect(screen.getByText("Skenario Bullish")).toBeInTheDocument();
      expect(screen.getByText("tinggi")).toBeInTheDocument();
      expect(screen.getByText("Sepakat Sinyal Engine")).toBeInTheDocument();
      expect(screen.getByText("Harga Bitcoin berkonsolidasi di atas VWAP dengan momentum RSI bullish.")).toBeInTheDocument();
      expect(screen.getByText("Harga bertahan di atas VWAP 81250")).toBeInTheDocument();
      expect(screen.getByText("Skenario Bearish")).toBeInTheDocument();
      expect(screen.getByText("81,250.00")).toBeInTheDocument();
    });
  });

  it("triggers AI request when user clicks Minta Analisa AI", async () => {
    let postTriggered = false;

    global.fetch = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : "url" in input ? input.url : String(input);
      const method =
        init?.method ||
        (typeof input === "object" && "method" in input ? (input as Request).method : "GET");

      if (url.includes("/api/analysis/BTCUSDT/ai")) {
        if (method === "POST") {
          postTriggered = true;
          return Promise.resolve(
            new Response(JSON.stringify(mockCommentResponse), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            })
          );
        }
        return Promise.resolve(new Response(JSON.stringify(null), { status: 404 }));
      }
      if (url.includes("/api/ai/quota")) {
        return Promise.resolve(
          new Response(JSON.stringify(mockQuotaResponse), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });

    render(<AICommentPanel symbol="BTCUSDT" tf="M15" />);

    const button = await screen.findByRole("button", { name: /Minta Analisa AI/i });
    expect(button).toBeInTheDocument();

    fireEvent.click(button);

    await waitFor(() => {
      expect(postTriggered).toBe(true);
      expect(screen.getByText("Skenario Bullish")).toBeInTheDocument();
    });
  });
});
