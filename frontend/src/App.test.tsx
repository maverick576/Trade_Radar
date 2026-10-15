import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

describe("App placeholder component", () => {
  it("renders TradeRadar header and title", async () => {
    // Mock global fetch to return sample healthy response
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: "healthy",
        version: "0.1.0",
        timestamp: "2026-10-15T00:00:00Z",
        infrastructure: {
          database: "healthy",
          redis: "healthy",
        },
        services: {
          api: { service: "api", status: "healthy", uptime_seconds: 10 },
          ingestor: { service: "ingestor", status: "healthy", uptime_seconds: 10 },
        },
      }),
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("TradeRadar")).toBeInTheDocument();
      expect(
        screen.getByText("Stack Container & Service Berjalan Normal")
      ).toBeInTheDocument();
    });
  });
});
