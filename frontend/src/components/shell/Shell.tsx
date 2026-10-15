import React, { useState, useEffect } from "react";
import { Sidebar, type NavItem } from "./Sidebar";
import { Topbar } from "./Topbar";
import { CommandPalette } from "./CommandPalette";
import { PasswordModal } from "../auth/PasswordModal";
import { TotpModal } from "../auth/TotpModal";
import { StatusPage } from "../../pages/StatusPage";
import { PlaceholderPage } from "../../pages/PlaceholderPage";
import { DashboardPage } from "../../pages/DashboardPage";
import { AnalisaPage } from "../../pages/AnalisaPage";
import { TicketPage } from "../../pages/TicketPage";
import { PaperPage } from "../../pages/PaperPage";
import { BriefPage } from "../../pages/BriefPage";
import { JurnalPage } from "../../pages/JurnalPage";

export const Shell: React.FC = () => {
  const [currentNav, setCurrentNav] = useState<NavItem>("dashboard");
  const [currentSymbol, setCurrentSymbol] = useState<string>("XAUUSD");
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);

  // Modals state
  const [commandPaletteOpen, setCommandPaletteOpen] = useState<boolean>(false);
  const [passwordModalOpen, setPasswordModalOpen] = useState<boolean>(false);
  const [totpModalOpen, setTotpModalOpen] = useState<boolean>(false);

  // Global Keyboard Shortcuts (Ctrl+K, 1-4 for symbols, / for command palette)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const isInput =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.isContentEditable;

      // Ctrl+K or Cmd+K
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
        return;
      }

      // If typing in input, don't hijack alphanumeric keys
      if (isInput) return;

      // '/' opens command palette
      if (e.key === "/") {
        e.preventDefault();
        setCommandPaletteOpen(true);
      }

      // '1'..'4' switch symbols
      const symbols = ["XAUUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"];
      const keyNum = parseInt(e.key, 10);
      if (!isNaN(keyNum) && keyNum >= 1 && keyNum <= symbols.length) {
        e.preventDefault();
        setCurrentSymbol(symbols[keyNum - 1]);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="min-h-screen bg-bg text-fg flex flex-row">
      {/* Sidebar */}
      <Sidebar
        currentNav={currentNav}
        onSelectNav={(item) => setCurrentNav(item)}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar
          currentSymbol={currentSymbol}
          onSelectSymbol={(sym) => setCurrentSymbol(sym)}
          onOpenCommandPalette={() => setCommandPaletteOpen(true)}
          onOpenPasswordModal={() => setPasswordModalOpen(true)}
          onOpenTotpModal={() => setTotpModalOpen(true)}
        />

        <main className="flex-1 p-4 md:p-6 lg:p-8 overflow-y-auto">
          <div className="max-w-7xl mx-auto">
            {currentNav === "dashboard" ? (
              <DashboardPage
                onSelectSymbol={(sym) => setCurrentSymbol(sym)}
                onNavigateToAnalisa={() => setCurrentNav("analisa")}
                onNavigateToTicket={() => setCurrentNav("ticket")}
              />
            ) : currentNav === "analisa" ? (
              <AnalisaPage
                symbol={currentSymbol}
                onSelectSymbol={(sym) => setCurrentSymbol(sym)}
              />
            ) : currentNav === "ticket" ? (
              <TicketPage initialSymbol={currentSymbol} />
            ) : currentNav === "paper" ? (
              <PaperPage />
            ) : currentNav === "jurnal" ? (
              <JurnalPage />
            ) : currentNav === "brief" ? (
              <BriefPage />
            ) : currentNav === "status" ? (
              <StatusPage />
            ) : (
              <PlaceholderPage page={currentNav} symbol={currentSymbol} />
            )}
          </div>
        </main>
      </div>

      {/* Modals & Dialogs */}
      <CommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        onNavigate={(item) => setCurrentNav(item)}
        onSelectSymbol={(sym) => setCurrentSymbol(sym)}
      />

      <PasswordModal
        isOpen={passwordModalOpen}
        onClose={() => setPasswordModalOpen(false)}
      />

      <TotpModal
        isOpen={totpModalOpen}
        onClose={() => setTotpModalOpen(false)}
      />
    </div>
  );
};
