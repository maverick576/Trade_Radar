import React from "react";
import { ThemeProvider } from "./context/ThemeContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { MarketProvider } from "./context/MarketContext";
import { LoginPage } from "./pages/LoginPage";
import { Shell } from "./components/shell/Shell";
import { Radar } from "lucide-react";

const AppContent: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen w-full flex flex-col items-center justify-center bg-bg text-fg p-4">
        <div className="w-16 h-16 rounded-2xl bg-surface border border-border shadow-xl flex items-center justify-center text-accent mb-4">
          <Radar className="w-9 h-9 animate-spin text-accent" aria-hidden="true" />
        </div>
        <span className="text-sm font-semibold tracking-wide text-fg animate-pulse">
          Memuat TradeRadar...
        </span>
        <span className="text-xs text-muted mt-1">Menghubungkan ke sesi aman</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <MarketProvider>
      <Shell />
    </MarketProvider>
  );
};

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ThemeProvider>
  );
}
