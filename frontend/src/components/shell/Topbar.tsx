import React, { useEffect, useState, useRef } from "react";
import {
  Sun,
  Moon,
  Laptop,
  Search,
  User as UserIcon,
  LogOut,
  Key,
  Shield,
  ChevronDown,
  Clock,
  Radio,
} from "lucide-react";
import { useTheme, type Theme } from "../../context/ThemeContext";
import { useAuth } from "../../context/AuthContext";

interface TopbarProps {
  currentSymbol: string;
  onSelectSymbol: (symbol: string) => void;
  onOpenCommandPalette: () => void;
  onOpenPasswordModal: () => void;
  onOpenTotpModal: () => void;
}

export const Topbar: React.FC<TopbarProps> = ({
  currentSymbol,
  onSelectSymbol,
  onOpenCommandPalette,
  onOpenPasswordModal,
  onOpenTotpModal,
}) => {
  const { theme, setTheme } = useTheme();
  const { user, logout } = useAuth();

  const [timeWib, setTimeWib] = useState<string>("");
  const [userMenuOpen, setUserMenuOpen] = useState<boolean>(false);
  const [themeMenuOpen, setThemeMenuOpen] = useState<boolean>(false);

  const userMenuRef = useRef<HTMLDivElement>(null);
  const themeMenuRef = useRef<HTMLDivElement>(null);

  const symbols = [
    { id: "XAUUSDT", label: "XAUUSDT", asset: "Gold" },
    { id: "BTCUSDT", label: "BTCUSDT", asset: "Crypto" },
    { id: "ETHUSDT", label: "ETHUSDT", asset: "Crypto" },
    { id: "SOLUSDT", label: "SOLUSDT", asset: "Crypto" },
  ];

  // Live WIB clock
  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      // Format in Asia/Jakarta timezone
      const formatter = new Intl.DateTimeFormat("id-ID", {
        timeZone: "Asia/Jakarta",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
      setTimeWib(`${formatter.format(now)} WIB`);
    };

    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  // Close menus on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
      if (themeMenuRef.current && !themeMenuRef.current.contains(e.target as Node)) {
        setThemeMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <header className="h-16 bg-surface border-b border-border px-4 flex items-center justify-between sticky top-0 z-20 gap-4">
      {/* Left: Symbol Quick Selector */}
      <div className="flex items-center gap-2 overflow-x-auto py-1">
        <span className="text-xs font-semibold text-muted uppercase tracking-wider hidden sm:inline-block mr-1">
          Simbol:
        </span>
        <div className="flex items-center bg-surface-2 p-1 rounded-btn border border-border">
          {symbols.map((s) => {
            const isSelected = currentSymbol === s.id;
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => onSelectSymbol(s.id)}
                className={`px-3 py-1 text-xs font-mono font-medium rounded transition-colors select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                  isSelected
                    ? "bg-surface text-accent shadow-sm font-semibold border border-border"
                    : "text-muted hover:text-fg"
                }`}
              >
                {s.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Center: Command Palette Trigger */}
      <div className="flex-1 max-w-xs hidden md:block">
        <button
          type="button"
          onClick={onOpenCommandPalette}
          className="w-full flex items-center justify-between px-3 py-1.5 rounded-btn bg-surface-2 border border-border text-xs text-muted hover:text-fg hover:border-muted/50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <span className="flex items-center gap-2">
            <Search className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Cari simbol, analisa, aksi...</span>
          </span>
          <kbd className="px-1.5 py-0.5 text-[10px] bg-surface rounded border border-border font-mono">
            Ctrl+K
          </kbd>
        </button>
      </div>

      {/* Right side items: Connection indicator, Clock, Theme, Account */}
      <div className="flex items-center gap-3">
        {/* Connection status */}
        <div
          title="Koneksi WebSocket & API aktif"
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-bull/10 border border-bull/20 text-bull text-[11px] font-medium"
        >
          <Radio className="w-3 h-3 animate-pulse" aria-hidden="true" />
          <span className="hidden lg:inline">Live</span>
          <span className="font-mono tabular-nums">24ms</span>
        </div>

        {/* Live WIB Clock */}
        <div
          title="Waktu Indonesia Barat (WIB)"
          className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-btn bg-surface-2 border border-border text-fg text-xs font-mono tabular-nums"
        >
          <Clock className="w-3.5 h-3.5 text-muted" aria-hidden="true" />
          <span>{timeWib || "00:00:00 WIB"}</span>
        </div>

        {/* Mobile Search button */}
        <button
          type="button"
          onClick={onOpenCommandPalette}
          aria-label="Buka pencarian perintah"
          className="md:hidden p-2 rounded-btn bg-surface-2 text-muted hover:text-fg border border-border"
        >
          <Search className="w-4 h-4" aria-hidden="true" />
        </button>

        {/* Theme selector dropdown */}
        <div className="relative" ref={themeMenuRef}>
          <button
            type="button"
            onClick={() => setThemeMenuOpen(!themeMenuOpen)}
            aria-label="Pilih tema tampilan"
            className="p-2 rounded-btn bg-surface-2 text-muted hover:text-fg border border-border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            {theme === "dark" ? (
              <Moon className="w-4 h-4 text-accent" aria-hidden="true" />
            ) : theme === "light" ? (
              <Sun className="w-4 h-4 text-warn" aria-hidden="true" />
            ) : (
              <Laptop className="w-4 h-4 text-muted" aria-hidden="true" />
            )}
          </button>

          {themeMenuOpen && (
            <div
              role="menu"
              className="absolute right-0 mt-2 w-36 bg-surface border border-border rounded-btn shadow-xl py-1 text-xs z-50 animate-scaleUp"
            >
              {(
                [
                  { id: "dark", label: "Gelap", icon: Moon },
                  { id: "light", label: "Terang", icon: Sun },
                  { id: "auto", label: "Otomatis", icon: Laptop },
                ] as Array<{ id: Theme; label: string; icon: React.FC<{ className?: string }> }>
              ).map((t) => {
                const Icon = t.icon;
                return (
                  <button
                    key={t.id}
                    role="menuitem"
                    type="button"
                    onClick={() => {
                      setTheme(t.id);
                      setThemeMenuOpen(false);
                    }}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 text-left transition-colors ${
                      theme === t.id
                        ? "bg-accent/15 text-accent font-semibold"
                        : "text-muted hover:text-fg hover:bg-surface-2"
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" aria-hidden="true" />
                    <span>{t.label}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* User Account menu */}
        <div className="relative" ref={userMenuRef}>
          <button
            type="button"
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            aria-expanded={userMenuOpen}
            aria-haspopup="true"
            aria-label="Menu akun pengguna"
            className="flex items-center gap-2 pl-2 pr-2.5 py-1.5 rounded-btn bg-surface-2 border border-border text-xs text-fg hover:bg-surface-2/80 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            <div className="w-6 h-6 rounded-full bg-accent/20 border border-accent/40 flex items-center justify-center text-accent">
              <UserIcon className="w-3.5 h-3.5" aria-hidden="true" />
            </div>
            <span className="hidden md:inline font-medium max-w-[120px] truncate">
              {user?.email || "Admin"}
            </span>
            <ChevronDown className="w-3.5 h-3.5 text-muted" aria-hidden="true" />
          </button>

          {userMenuOpen && (
            <div
              role="menu"
              className="absolute right-0 mt-2 w-52 bg-surface border border-border rounded-panel shadow-2xl py-1.5 text-xs z-50 animate-scaleUp"
            >
              <div className="px-3.5 py-2 border-b border-border">
                <span className="text-[11px] text-muted block">Masuk sebagai</span>
                <span className="font-semibold text-fg block truncate">{user?.email}</span>
                <div className="mt-1 flex items-center gap-1.5">
                  <span
                    className={`inline-block w-2 h-2 rounded-full ${
                      user?.totp_enabled ? "bg-bull" : "bg-neutral"
                    }`}
                  />
                  <span className="text-[10px] text-muted">
                    {user?.totp_enabled ? "2FA Aktif" : "2FA Tidak Aktif"}
                  </span>
                </div>
              </div>

              <div className="py-1">
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setUserMenuOpen(false);
                    onOpenPasswordModal();
                  }}
                  className="w-full flex items-center gap-2.5 px-3.5 py-2 text-left text-muted hover:text-fg hover:bg-surface-2 transition-colors"
                >
                  <Key className="w-3.5 h-3.5" aria-hidden="true" />
                  <span>Ubah Kata Sandi</span>
                </button>

                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setUserMenuOpen(false);
                    onOpenTotpModal();
                  }}
                  className="w-full flex items-center gap-2.5 px-3.5 py-2 text-left text-muted hover:text-fg hover:bg-surface-2 transition-colors"
                >
                  <Shield className="w-3.5 h-3.5" aria-hidden="true" />
                  <span>Pengaturan 2FA (TOTP)</span>
                </button>
              </div>

              <div className="pt-1 border-t border-border">
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setUserMenuOpen(false);
                    void logout();
                  }}
                  className="w-full flex items-center gap-2.5 px-3.5 py-2 text-left text-bear hover:bg-bear/10 transition-colors font-medium"
                >
                  <LogOut className="w-3.5 h-3.5" aria-hidden="true" />
                  <span>Keluar dari Akun</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
