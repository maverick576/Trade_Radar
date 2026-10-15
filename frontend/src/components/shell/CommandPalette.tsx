import React, { useEffect, useState, useRef } from "react";
import {
  Search,
  LayoutDashboard,
  LineChart,
  Ticket,
  Wallet,
  BookOpen,
  Newspaper,
  Calendar,
  Activity,
  Settings,
  Sparkles,
  Sliders,
  X,
} from "lucide-react";
import type { NavItem } from "./Sidebar";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (item: NavItem) => void;
  onSelectSymbol: (symbol: string) => void;
}

interface ActionItem {
  id: string;
  title: string;
  category: "Halaman" | "Simbol" | "Aksi Cepat";
  icon: React.FC<{ className?: string }>;
  handler: () => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onNavigate,
  onSelectSymbol,
}) => {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const actions: ActionItem[] = [
    // Halaman
    {
      id: "page-status",
      title: "Buka Status Sistem & Layanan",
      category: "Halaman",
      icon: Activity,
      handler: () => onNavigate("status"),
    },
    {
      id: "page-dashboard",
      title: "Buka Dashboard Ringkasan",
      category: "Halaman",
      icon: LayoutDashboard,
      handler: () => onNavigate("dashboard"),
    },
    {
      id: "page-analisa",
      title: "Buka Analisa Multi-Indikator & Chart",
      category: "Halaman",
      icon: LineChart,
      handler: () => onNavigate("analisa"),
    },
    {
      id: "page-ticket",
      title: "Buka Trade Ticket & Sinyal Aktif",
      category: "Halaman",
      icon: Ticket,
      handler: () => onNavigate("ticket"),
    },
    {
      id: "page-paper",
      title: "Buka Jurnal Posisi Paper Trading",
      category: "Halaman",
      icon: Wallet,
      handler: () => onNavigate("paper"),
    },
    {
      id: "page-jurnal",
      title: "Buka Jurnal & Statistik Winrate",
      category: "Halaman",
      icon: BookOpen,
      handler: () => onNavigate("jurnal"),
    },
    {
      id: "page-brief",
      title: "Buka Market Brief Harian AI",
      category: "Halaman",
      icon: Newspaper,
      handler: () => onNavigate("brief"),
    },
    {
      id: "page-kalender",
      title: "Buka Kalender Berita Ekonomi",
      category: "Halaman",
      icon: Calendar,
      handler: () => onNavigate("kalender"),
    },
    {
      id: "page-pengaturan",
      title: "Buka Pengaturan & Strategi",
      category: "Halaman",
      icon: Settings,
      handler: () => onNavigate("pengaturan"),
    },

    // Simbol
    {
      id: "sym-xau",
      title: "Pilih Simbol: XAUUSDT (Gold Perpetual)",
      category: "Simbol",
      icon: LineChart,
      handler: () => {
        onSelectSymbol("XAUUSDT");
        onNavigate("analisa");
      },
    },
    {
      id: "sym-btc",
      title: "Pilih Simbol: BTCUSDT (Bitcoin)",
      category: "Simbol",
      icon: LineChart,
      handler: () => {
        onSelectSymbol("BTCUSDT");
        onNavigate("analisa");
      },
    },
    {
      id: "sym-eth",
      title: "Pilih Simbol: ETHUSDT (Ethereum)",
      category: "Simbol",
      icon: LineChart,
      handler: () => {
        onSelectSymbol("ETHUSDT");
        onNavigate("analisa");
      },
    },
    {
      id: "sym-sol",
      title: "Pilih Simbol: SOLUSDT (Solana)",
      category: "Simbol",
      icon: LineChart,
      handler: () => {
        onSelectSymbol("SOLUSDT");
        onNavigate("analisa");
      },
    },

    // Aksi
    {
      id: "act-ai",
      title: "Minta Komentar AI Gemini (Analisa Terkini)",
      category: "Aksi Cepat",
      icon: Sparkles,
      handler: () => onNavigate("analisa"),
    },
    {
      id: "act-brief-gen",
      title: "Buat Market Brief Baru (On-demand)",
      category: "Aksi Cepat",
      icon: Newspaper,
      handler: () => onNavigate("brief"),
    },
    {
      id: "act-calib",
      title: "Kalibrasi Harga Broker Terhadap Sumber",
      category: "Aksi Cepat",
      icon: Sliders,
      handler: () => onNavigate("ticket"),
    },
  ];

  const filtered = actions.filter((act) =>
    act.title.toLowerCase().includes(query.toLowerCase().trim())
  );

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1 < filtered.length ? prev + 1 : 0));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 >= 0 ? prev - 1 : filtered.length - 1));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (filtered[selectedIndex]) {
          filtered[selectedIndex].handler();
          onClose();
        }
      } else if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, filtered, selectedIndex, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4 bg-black/60 backdrop-blur-sm animate-fadeIn"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Palet Perintah"
        className="w-full max-w-xl bg-surface border border-border rounded-panel shadow-2xl overflow-hidden animate-scaleUp"
      >
        {/* Search Input Bar */}
        <div className="flex items-center px-4 py-3.5 border-b border-border gap-3 bg-surface">
          <Search className="w-4 h-4 text-muted shrink-0" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Ketik perintah atau nama halaman (misal: 'status', 'xau', 'ai')..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            className="w-full bg-transparent text-sm text-fg placeholder:text-muted/60 focus:outline-none"
          />
          <button
            type="button"
            onClick={onClose}
            aria-label="Tutup pencarian"
            className="text-muted hover:text-fg p-1 rounded hover:bg-surface-2"
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        {/* Action list */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filtered.length === 0 ? (
            <div className="py-8 text-center text-xs text-muted">
              Tidak ada perintah yang cocok dengan &ldquo;{query}&rdquo;
            </div>
          ) : (
            filtered.map((item, idx) => {
              const Icon = item.icon;
              const isSelected = selectedIndex === idx;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    item.handler();
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-btn text-xs transition-colors text-left select-none ${
                    isSelected ? "bg-accent/15 text-accent font-medium" : "text-fg hover:bg-surface-2"
                  }`}
                >
                  <div className="flex items-center gap-3 overflow-hidden">
                    <Icon className="w-4 h-4 shrink-0 text-muted" aria-hidden="true" />
                    <span className="truncate">{item.title}</span>
                  </div>
                  <span className="text-[10px] text-muted uppercase tracking-wider font-mono shrink-0 ml-2">
                    {item.category}
                  </span>
                </button>
              );
            })
          )}
        </div>

        {/* Footer shortcuts */}
        <div className="px-4 py-2 border-t border-border bg-surface-2 flex items-center justify-between text-[11px] text-muted">
          <div className="flex items-center gap-3">
            <span>
              <kbd className="px-1 py-0.5 bg-surface border border-border rounded text-[10px]">↑↓</kbd> navigasi
            </span>
            <span>
              <kbd className="px-1 py-0.5 bg-surface border border-border rounded text-[10px]">Enter</kbd> pilih
            </span>
          </div>
          <span>
            <kbd className="px-1 py-0.5 bg-surface border border-border rounded text-[10px]">Esc</kbd> tutup
          </span>
        </div>
      </div>
    </div>
  );
};
