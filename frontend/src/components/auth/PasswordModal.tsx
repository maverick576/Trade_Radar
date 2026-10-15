import React, { useState } from "react";
import { Dialog } from "../ui/Dialog";
import { Input } from "../ui/Input";
import { Button } from "../ui/Button";
import { api } from "../../api/client";
import { AlertCircle, CheckCircle2 } from "lucide-react";

interface PasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const PasswordModal: React.FC<PasswordModalProps> = ({ isOpen, onClose }) => {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleClose = () => {
    setOldPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setError(null);
    setSuccess(null);
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (newPassword.length < 8) {
      setError("Kata sandi baru minimal 8 karakter.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("Konfirmasi kata sandi baru tidak cocok.");
      return;
    }

    setLoading(true);
    try {
      const { data, error: apiError } = await api.PUT("/api/auth/password", {
        body: {
          old_password: oldPassword,
          new_password: newPassword,
        },
      });

      if (apiError || !data) {
        const errDetail = apiError as { error?: { message?: string } };
        setError(errDetail?.error?.message || "Gagal memperbarui kata sandi.");
      } else {
        setSuccess(data.message || "Kata sandi berhasil diperbarui.");
        setTimeout(() => {
          handleClose();
        }, 1500);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Terjadi kesalahan pada server.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={handleClose}
      title="Ubah Kata Sandi"
      description="Pastikan kata sandi baru Anda kuat dan sulit ditebak."
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

      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          id="old-password"
          label="Kata Sandi Saat Ini"
          type="password"
          required
          autoComplete="current-password"
          value={oldPassword}
          onChange={(e) => setOldPassword(e.target.value)}
          disabled={loading}
        />

        <Input
          id="new-password"
          label="Kata Sandi Baru (Min. 8 Karakter)"
          type="password"
          required
          autoComplete="new-password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          disabled={loading}
        />

        <Input
          id="confirm-password"
          label="Konfirmasi Kata Sandi Baru"
          type="password"
          required
          autoComplete="new-password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          disabled={loading}
        />

        <div className="flex items-center justify-end gap-3 pt-3">
          <Button type="button" variant="ghost" onClick={handleClose} disabled={loading}>
            Batal
          </Button>
          <Button type="submit" variant="primary" loading={loading}>
            Simpan Perubahan
          </Button>
        </div>
      </form>
    </Dialog>
  );
};
