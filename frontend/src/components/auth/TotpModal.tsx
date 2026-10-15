import React, { useEffect, useState } from "react";
import { Dialog } from "../ui/Dialog";
import { Input } from "../ui/Input";
import { Button } from "../ui/Button";
import { api } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { AlertCircle, CheckCircle2, Copy, Shield, ShieldOff, Check } from "lucide-react";

interface TotpModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const TotpModal: React.FC<TotpModalProps> = ({ isOpen, onClose }) => {
  const { user, checkAuth } = useAuth();
  const isEnabled = Boolean(user?.totp_enabled);

  // Setup state
  const [secret, setSecret] = useState<string>("");
  const [otpauthUrl, setOtpauthUrl] = useState<string>("");
  const [verifyCode, setVerifyCode] = useState<string>("");
  const [copied, setCopied] = useState<boolean>(false);

  // Disable state
  const [disablePassword, setDisablePassword] = useState<string>("");
  const [disableCode, setDisableCode] = useState<string>("");

  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && !isEnabled) {
      void fetchSetup();
    }
    if (isOpen) {
      setError(null);
      setSuccess(null);
      setVerifyCode("");
      setDisablePassword("");
      setDisableCode("");
      setCopied(false);
    }
  }, [isOpen, isEnabled]);

  const fetchSetup = async () => {
    setLoading(true);
    try {
      const { data, error: apiErr } = await api.POST("/api/auth/totp/setup");
      if (data && !apiErr) {
        setSecret(data.secret);
        setOtpauthUrl(data.otpauth_url);
      } else {
        const errDetail = apiErr as { error?: { message?: string } };
        setError(errDetail?.error?.message || "Gagal memuat konfigurasi 2FA.");
      }
    } catch {
      setError("Tidak dapat menghubungi server.");
    } finally {
      setLoading(false);
    }
  };

  const handleCopySecret = async () => {
    if (!secret) return;
    try {
      await navigator.clipboard.writeText(secret);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  const handleEnable = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!verifyCode || verifyCode.length < 6) {
      setError("Masukkan 6 digit kode dari aplikasi autentikator.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const { data, error: apiErr } = await api.POST("/api/auth/totp/verify", {
        body: { secret, code: verifyCode },
      });

      if (apiErr || !data) {
        const errDetail = apiErr as { error?: { message?: string } };
        setError(errDetail?.error?.message || "Kode 2FA tidak valid.");
      } else {
        setSuccess("2FA TOTP berhasil diaktifkan!");
        await checkAuth();
        setTimeout(() => {
          onClose();
        }, 1500);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  };

  const handleDisable = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!disablePassword || !disableCode) {
      setError("Lengkapi kata sandi dan kode 2FA untuk menonaktifkan.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const { data, error: apiErr } = await api.POST("/api/auth/totp/disable", {
        body: { password: disablePassword, code: disableCode },
      });

      if (apiErr || !data) {
        const errDetail = apiErr as { error?: { message?: string } };
        setError(errDetail?.error?.message || "Gagal menonaktifkan 2FA.");
      } else {
        setSuccess("2FA TOTP berhasil dinonaktifkan.");
        await checkAuth();
        setTimeout(() => {
          onClose();
        }, 1500);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Terjadi kesalahan.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title={isEnabled ? "Nonaktifkan Autentikasi 2FA" : "Aktifkan Autentikasi 2FA (TOTP)"}
      description={
        isEnabled
          ? "Akun Anda saat ini terlindungi dengan verifikasi dua langkah."
          : "Tingkatkan keamanan akun Anda dengan Google Authenticator atau aplikasi sejenis."
      }
      maxWidth="md"
    >
      {error && (
        <div
          role="alert"
          className="mb-4 p-3 rounded-btn bg-bear/10 border border-bear/30 flex items-start gap-2.5 text-bear text-xs"
        >
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div
          role="status"
          className="mb-4 p-3 rounded-btn bg-bull/10 border border-bull/30 flex items-start gap-2.5 text-bull text-xs font-medium"
        >
          <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
          <span>{success}</span>
        </div>
      )}

      {!isEnabled ? (
        <form onSubmit={handleEnable} className="space-y-4">
          <div className="bg-surface-2 p-3.5 rounded-btn border border-border space-y-2">
            <span className="text-xs text-muted block font-medium">Kunci Rahasia (Secret Key):</span>
            <div className="flex items-center justify-between gap-2 bg-surface px-3 py-2 rounded border border-border">
              <code className="text-xs font-mono font-bold tracking-wider text-accent break-all select-all">
                {secret || "Memuat..."}
              </code>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleCopySecret}
                disabled={!secret}
                className="shrink-0"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-bull" aria-hidden="true" />
                    <span>Tersalin</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" aria-hidden="true" />
                    <span>Salin</span>
                  </>
                )}
              </Button>
            </div>
            <p className="text-[11px] text-muted">
              Masukkan kunci di atas ke Google Authenticator, Bitwarden, atau 1Password dengan memilih opsi &ldquo;Manual Entry&rdquo;.
            </p>
            {otpauthUrl && (
              <a
                href={otpauthUrl}
                className="text-[11px] text-accent hover:underline block truncate mt-1"
                title={otpauthUrl}
              >
                Buka link autentikator langsung (otpauth://)
              </a>
            )}
          </div>

          <Input
            id="totp-code-input"
            label="Kode Verifikasi 6-Digit"
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={6}
            placeholder="000000"
            required
            value={verifyCode}
            onChange={(e) => setVerifyCode(e.target.value.trim())}
            disabled={loading}
            helperText="Masukkan kode yang tampil di aplikasi autentikator Anda."
          />

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button type="button" variant="ghost" onClick={onClose} disabled={loading}>
              Batal
            </Button>
            <Button type="submit" variant="primary" loading={loading} disabled={!secret}>
              <Shield className="w-4 h-4 mr-1.5" aria-hidden="true" />
              Verifikasi & Aktifkan
            </Button>
          </div>
        </form>
      ) : (
        <form onSubmit={handleDisable} className="space-y-4">
          <div className="bg-warn/10 p-3.5 rounded-btn border border-warn/30 text-xs text-warn">
            Peringatan: Menonaktifkan 2FA akan mengurangi keamanan akun Anda. Anda akan diminta memasukkan kata sandi dan kode TOTP saat ini.
          </div>

          <Input
            id="disable-password"
            label="Kata Sandi Akun"
            type="password"
            required
            autoComplete="current-password"
            value={disablePassword}
            onChange={(e) => setDisablePassword(e.target.value)}
            disabled={loading}
          />

          <Input
            id="disable-totp-code"
            label="Kode 2FA TOTP Saat Ini"
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={6}
            placeholder="000000"
            required
            value={disableCode}
            onChange={(e) => setDisableCode(e.target.value.trim())}
            disabled={loading}
          />

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button type="button" variant="ghost" onClick={onClose} disabled={loading}>
              Batal
            </Button>
            <Button type="submit" variant="danger" loading={loading}>
              <ShieldOff className="w-4 h-4 mr-1.5" aria-hidden="true" />
              Nonaktifkan 2FA
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  );
};
