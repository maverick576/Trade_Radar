import React, { createContext, useContext, useEffect, useState } from "react";
import { api, type LoginPayload, type UserProfile } from "../api/client";

interface LoginResult {
  success: boolean;
  requires2fa?: boolean;
  message?: string;
}

interface AuthContextType {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  checkAuth: () => Promise<void>;
  login: (payload: LoginPayload) => Promise<LoginResult>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const checkAuth = async () => {
    try {
      const { data, error } = await api.GET("/api/auth/me");
      if (data && !error) {
        setUser(data);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch {
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void checkAuth();
  }, []);

  const login = async (payload: LoginPayload): Promise<LoginResult> => {
    try {
      const { data, error, response } = await api.POST("/api/auth/login", {
        body: payload,
      });

      if (response.status === 429) {
        return {
          success: false,
          message:
            (error as { error?: { message?: string } })?.error?.message ||
            "Terlalu banyak percobaan login. Coba lagi beberapa saat lagi.",
        };
      }

      if (error || !data) {
        const errorDetail = error as { error?: { message?: string } };
        return {
          success: false,
          message: errorDetail?.error?.message || "Email atau kata sandi tidak valid.",
        };
      }

      if (data.requires_2fa) {
        return {
          success: false,
          requires2fa: true,
          message: data.message || "Kode 2FA TOTP diperlukan.",
        };
      }

      if (data.user) {
        setUser(data.user);
        setIsAuthenticated(true);
        return {
          success: true,
          message: data.message || "Login berhasil.",
        };
      }

      return { success: false, message: "Terjadi kesalahan saat memproses login." };
    } catch (err: unknown) {
      return {
        success: false,
        message: err instanceof Error ? err.message : "Tidak dapat terhubung ke server.",
      };
    }
  };

  const logout = async () => {
    try {
      await api.POST("/api/auth/logout");
    } finally {
      setUser(null);
      setIsAuthenticated(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isLoading,
        checkAuth,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
