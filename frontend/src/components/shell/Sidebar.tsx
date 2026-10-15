import React from "react";
import {
  LayoutDashboard,
  LineChart,
  Ticket,
  Wallet,
  BookOpen,
  Newspaper,
  Calendar,
  Activity,
  Settings,
  ChevronLeft,
  ChevronRight,
  Radar,
} from "lucide-react";

export type NavItem =
  | "dashboard"
  | "analisa"
  | "ticket"
  | "paper"
  | "jurnal"
  | "brief"
  | "kalender"
  | "status"
  | "pengaturan";

interface SidebarProps {
  currentNav: NavItem;
  onSelectNav: (item: NavItem) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentNav,
  onSelectNav,
  collapsed,
  onToggleCollapse,
}) => {
  const navItems: Array<{ id: NavItem; label: string; icon: React.FC<{ className?: string }> }> = [
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    { id: "analisa", label: "Analisa", icon: LineChart },
    { id: "ticket", label: "Ticket & Sinyal", icon: Ticket },
    { id: "paper", label: "Posisi Paper", icon: Wallet },
    { id: "jurnal", label: "Jurnal & Winrate", icon: BookOpen },
    { id: "brief", label: "Market Brief", icon: Newspaper },
    { id: "kalender", label: "Kalender Berita", icon: Calendar },
    { id: "status", label: "Status Sistem", icon: Activity },
    { id: "pengaturan", label: "Pengaturan", icon: Settings },
  ];

  return (
    <aside
      aria-label="Navigasi Utama"
      className={`h-screen sticky top-0 bg-surface border-r border-border transition-all duration-300 flex flex-col justify-between z-30 shrink-0 ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      <div>
        {/* Header / Brand */}
        <div className="h-16 px-4 flex items-center justify-between border-b border-border">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="w-9 h-9 rounded-xl bg-surface-2 border border-border flex items-center justify-center text-accent shrink-0 shadow-sm">
              <Radar className="w-5 h-5 animate-pulse" aria-hidden="true" />
            </div>
            {!collapsed && (
              <div className="overflow-hidden whitespace-nowrap">
                <span className="font-bold text-base tracking-tight text-fg block">TradeRadar</span>
                <span className="text-[10px] text-muted font-medium uppercase tracking-wider block">
                  Terminal v0.1
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Navigation list */}
        <nav className="p-2 space-y-1 mt-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentNav === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelectNav(item.id)}
                title={collapsed ? item.label : undefined}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-btn text-xs font-medium transition-colors select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                  isActive
                    ? "bg-accent/15 text-accent font-semibold"
                    : "text-muted hover:text-fg hover:bg-surface-2"
                }`}
              >
                <Icon
                  className={`w-4 h-4 shrink-0 ${isActive ? "text-accent" : "text-muted"}`}
                  aria-hidden="true"
                />
                {!collapsed && (
                  <span className="whitespace-nowrap overflow-hidden text-ellipsis">
                    {item.label}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Collapse Toggle Footer */}
      <div className="p-3 border-t border-border flex items-center justify-end">
        <button
          type="button"
          onClick={onToggleCollapse}
          aria-label={collapsed ? "Perluas menu bilah sisi" : "Ciutkan menu bilah sisi"}
          className="w-full flex items-center justify-center p-2 rounded-btn text-muted hover:text-fg hover:bg-surface-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" aria-hidden="true" />
          ) : (
            <div className="flex items-center gap-2 text-xs font-medium w-full">
              <ChevronLeft className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span>Ciutkan Menu</span>
            </div>
          )}
        </button>
      </div>
    </aside>
  );
};
