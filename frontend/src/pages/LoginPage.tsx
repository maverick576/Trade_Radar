import React, { useState } from "react";
import { ShieldCheck, ArrowRight, KeyRound, AlertCircle, Radar } from "lucide-react";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Card } from "../components/ui/Card";
import { useAuth } from "../context/AuthContext";

export const LoginPage: React.FC = () => {
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [requires2fa, setRequires2fa] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setLoading(true);

    try {
      const result = await login({
        email,
        password,
        totp_code: requires2fa ? totpCode : null,
      });

      if (!result.success) {
        if (result.requires2fa) {
          setRequires2fa(true);
        } else {
          setErrorMessage(result.message || "Gagal masuk.");
        }
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen w-full flex items-center justify-center p-4 bg-bg text-fg">
      <div className="w-full max-w-md animate-fadeIn">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-surface border border-border shadow-md mb-4 text-accent">
            <Radar className="w-8 h-8 animate-pulse" aria-hidden="true" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-fg">
            TradeRadar
          </h1>
          <p className="text-sm text-muted mt-1.5">
            Terminal Analisis Konfluensi Pasar Crypto & Emas
          </p>
        </div>

        <Card className="shadow-xl border-border bg-surface">
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-fg">
              {requires2fa ? "Verifikasi Dua Langkah (2FA)" : "Masuk ke Akun"}
            </h2>
            <p className="text-xs text-muted mt-1">
              {requires2fa
                ? "Masukkan 6 digit kode dari aplikasi autentikator Anda."
                : "Gunakan akun administrator untuk mengakses terminal."}
            </p>
          </div>

          {errorMessage && (
            <div
              role="alert"
              aria-live="assertive"
              className="mb-5 p-3.5 rounded-btn bg-bear/10 border border-bear/30 flex items-start gap-3 text-bear text-xs font-medium"
            >
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
              <span>{errorMessage}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {!requires2fa ? (
              <>
                <Input
                  id="login-email"
                  name="email"
                  type="email"
                  label="Alamat Email"
                  placeholder="admin@example.com"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading}
                />
                <Input
                  id="login-password"
                  name="password"
                  type="password"
                  label="Kata Sandi"
                  placeholder="••••••••••••"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loading}
                />
              </>
            ) : (
              <div className="space-y-4 animate-fadeIn">
                <Input
                  id="login-totp"
                  name="totp_code"
                  type="text"
                  label="Kode Keamanan 2FA TOTP"
                  placeholder="Contoh: 123456"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={8}
                  autoComplete="one-time-code"
                  autoFocus
                  required
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value.trim())}
                  disabled={loading}
                  helperText="Buka Google Authenticator atau aplikasi sejenis untuk melihat kode aktif."
                />
              </div>
            )}

            <div className="pt-2">
              <Button
                type="submit"
                variant="primary"
                size="lg"
                loading={loading}
                className="w-full font-semibold"
              >
                {requires2fa ? (
                  <>
                    <KeyRound className="w-4 h-4 shrink-0" aria-hidden="true" />
                    <span>Verifikasi Kode & Masuk</span>
                  </>
                ) : (
                  <>
                    <span>Masuk ke Terminal</span>
                    <ArrowRight className="w-4 h-4 shrink-0" aria-hidden="true" />
                  </>
                )}
              </Button>
            </div>

            {requires2fa && (
              <div className="pt-2 text-center">
                <button
                  type="button"
                  onClick={() => {
                    setRequires2fa(false);
                    setTotpCode("");
                    setErrorMessage(null);
                  }}
                  className="text-xs text-muted hover:text-fg underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded p-1"
                >
                  Kembali ke pengisian email & kata sandi
                </button>
              </div>
            )}
          </form>

          <div className="mt-6 pt-5 border-t border-border flex items-center justify-between text-[11px] text-muted">
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-bull" aria-hidden="true" />
              Sesi terenkripsi & terlindungi CSRF
            </span>
            <span>Versi 0.1.0-dev</span>
          </div>
        </Card>
      </div>
    </main>
  );
};
