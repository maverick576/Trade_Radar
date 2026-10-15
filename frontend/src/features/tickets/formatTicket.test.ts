import { describe, expect, it } from "vitest";
import {
  formatIdNumber,
  formatCountdown,
  buildCompactCopyString,
} from "./formatTicket";
import type { TicketItem } from "../../api/client";

describe("formatTicket utilities", () => {
  it("formats numbers in Indonesian locale (dot for thousands, comma for decimals)", () => {
    expect(formatIdNumber(2651.0, 1)).toBe("2.651,0");
    expect(formatIdNumber(10000, 0)).toBe("10.000");
    expect(formatIdNumber(0.06, 2)).toBe("0,06");
    expect(formatIdNumber(1234567.89, 2)).toBe("1.234.567,89");
  });

  it("calculates countdown correctly and flags expiration", () => {
    const pastTime = new Date(Date.now() - 60000).toISOString();
    const futureTime = new Date(Date.now() + 125000).toISOString();

    const expiredResult = formatCountdown(pastTime);
    expect(expiredResult.isExpired).toBe(true);
    expect(expiredResult.text).toBe("Kedaluwarsa");

    const activeResult = formatCountdown(futureTime);
    expect(activeResult.isExpired).toBe(false);
    expect(activeResult.text).toMatch(/\d+m \d+s tersisa/);
  });

  it("builds compact copy string matching BLUEPRINT.md §5.3 specification", () => {
    const mockTicket: TicketItem = {
      id: 1,
      symbol: "XAUUSD",
      side: "LONG",
      strategy: "KONFLUENSI_10",
      score: 65,
      source: "binance",
      entry: 2651.0,
      entry_low: 2649.0,
      entry_high: 2653.0,
      sl: 2636.5,
      tp1: 2665.5,
      tp2: 2680.0,
      atr: 7.25,
      sl_points: 14.5,
      sl_atr_mult: 2.0,
      tp1_points: 14.5,
      tp2_points: 29.0,
      invalidation: "H1 Supertrend flip BEAR",
      reasons: ["Score 65/100"],
      risks: ["US Session Open"],
      suggested_lot: 0.06,
      actual_risk_usd: 87.0,
      actual_risk_pct: 0.87,
      min_lot_warning: false,
      valid_until: new Date(Date.now() + 300000).toISOString(),
      status: "new",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      text_full: "TIKET BUY XAUUSD",
      text_compact: "BUY XAUUSD 2651 SL 2636.5 TP 2665.5/2680 0.06lot",
    };

    // When text_compact is present on ticket
    expect(buildCompactCopyString(mockTicket)).toBe(
      "BUY XAUUSD 2651 SL 2636.5 TP 2665.5/2680 0.06lot"
    );

    // When lot is overridden by user
    expect(buildCompactCopyString(mockTicket, 0.1)).toBe(
      "BUY XAUUSD 2651 SL 2636.5 TP 2665.5/2680 0.1lot"
    );
  });
});
