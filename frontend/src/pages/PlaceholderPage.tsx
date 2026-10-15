import React from "react";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Construction } from "lucide-react";
import type { NavItem } from "../components/shell/Sidebar";

interface PlaceholderPageProps {
  page: NavItem;
  symbol: string;
}

const PAGE_META: Record<NavItem, { title: string; phase: string; desc: string }> = {
  dashboard: {
    title: "Dashboard Utama",
    phase: "Fase 2 & 4",
    desc: "Kartu watchlist live, gauge skor konfluensi -100..+100, ticket aktif, dan timeline berita.",
  },
  analisa: {
    title: "Analisa Pasar & Charting",
    phase: "Fase 2, 3, & 4",
    desc: "Lightweight-charts candlestick, 10 indikator teknikal & order flow, checklist macro, dan panel tanggapan AI.",
  },
  ticket: {
    title: "Trade Ticket & Sinyal Siap Eksekusi",
    phase: "Fase 5",
    desc: "Resume trade siap salin ke broker, kalibrasi offset broker, kalkulator lot, dan jurnal eksekusi nyata.",
  },
  paper: {
    title: "Posisi Paper Trading",
    phase: "Fase 5",
    desc: "Simulasi posisi otomatis berdasarkan sinyal STRONG konfluensi, trailing TP1 ke BE, dan kalkulasi PnL R.",
  },
  jurnal: {
    title: "Jurnal & Statistik Winrate",
    phase: "Fase 8",
    desc: "Buku trade paper vs real, akurasi per indikator, heatmap jam×hari, evaluasi macro filter, dan ekspor CSV.",
  },
  brief: {
    title: "Market Brief Harian AI",
    phase: "Fase 6",
    desc: "Brief pagi 06:45 WIB oleh AI Gemini: level kunci harian, bias H4/D1, skenario bullish/bearish, dan berita relevan.",
  },
  kalender: {
    title: "Kalender Berita Ekonomi",
    phase: "Fase 9",
    desc: "Jadwal event ekonomi berbobot tinggi (ForexFactory & Finnhub), countdown topbar, dan zona blackout sinyal.",
  },
  status: {
    title: "Status Sistem",
    phase: "Fase 1",
    desc: "Pemantauan layanan, container, database, redis, dan data pipeline.",
  },
  pengaturan: {
    title: "Pengaturan & Strategi",
    phase: "Fase 12",
    desc: "Konfigurasi watchlist, bobot indikator, ambang batas sinyal, profil broker, kuota AI, dan bot Telegram.",
  },
};

export const PlaceholderPage: React.FC<PlaceholderPageProps> = ({ page, symbol }) => {
  const meta = PAGE_META[page] || {
    title: "Halaman",
    phase: "Fase Mendatang",
    desc: "Fitur sedang dalam pengembangan.",
  };

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-xl md:text-2xl font-bold tracking-tight text-fg">{meta.title}</h1>
          <Badge variant="accent">{meta.phase}</Badge>
          {page === "analisa" && <Badge variant="neutral">{symbol}</Badge>}
        </div>
        <p className="text-xs text-muted mt-1">{meta.desc}</p>
      </div>

      <Card className="p-8 text-center border-dashed border-border flex flex-col items-center justify-center min-h-[360px]">
        <div className="w-14 h-14 rounded-2xl bg-surface-2 border border-border flex items-center justify-center text-muted mb-4">
          <Construction className="w-7 h-7 text-accent" aria-hidden="true" />
        </div>
        <h2 className="text-base font-semibold text-fg">Modul Terjadwal pada {meta.phase}</h2>
        <p className="text-xs text-muted max-w-md mt-1.5 leading-relaxed">
          Fondasi sistem, autentikasi sesi, rate-limiting, CSRF, dan shell UI telah aktif sempurna.
          Modul ini akan diaktifkan secara bertahap sesuai urutan pada roadmap eksekusi.
        </p>
      </Card>
    </div>
  );
};
