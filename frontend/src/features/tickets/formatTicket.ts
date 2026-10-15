/**
 * Helpers for formatting Trade Tickets according to Indonesian locale
 * and BLUEPRINT.md §5.3 specification.
 */

import type { TicketItem } from "../../api/client";

export function formatIdNumber(val: number, decimals: number = 1): string {
  const parts = val.toFixed(decimals).split(".");
  const intPart = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return parts.length > 1 ? `${intPart},${parts[1]}` : intPart;
}

export function formatCountdown(validUntilIso: string): { text: string; isExpired: boolean } {
  const now = new Date().getTime();
  const validUntil = new Date(validUntilIso).getTime();
  const diffSec = Math.floor((validUntil - now) / 1000);

  if (diffSec <= 0) {
    return { text: "Kedaluwarsa", isExpired: true };
  }

  const mins = Math.floor(diffSec / 60);
  const secs = diffSec % 60;
  return {
    text: `${mins}m ${secs.toString().padStart(2, "0")}s tersisa`,
    isExpired: false,
  };
}

export function copyToClipboard(text: string): Promise<boolean> {
  if (navigator?.clipboard?.writeText) {
    return navigator.clipboard.writeText(text).then(
      () => true,
      () => false
    );
  }
  return Promise.resolve(false);
}

export function buildCompactCopyString(ticket: TicketItem, lotOverride?: number): string {
  if (ticket.text_compact && !lotOverride) {
    return ticket.text_compact;
  }
  const action = ticket.side === "LONG" ? "BUY" : "SELL";
  const lot = lotOverride || ticket.suggested_lot || 0.01;
  const lotStr = lot >= 0.1 ? lot.toFixed(2).replace(/\.?0+$/, "") : lot.toFixed(2);
  const entryStr = ticket.entry.toString();
  const slStr = ticket.sl.toString();
  const tp1Str = ticket.tp1.toString();
  const tp2Str = ticket.tp2.toString();

  return `${action} ${ticket.symbol} ${entryStr} SL ${slStr} TP ${tp1Str}/${tp2Str} ${lotStr}lot`;
}
