"use client";

import React, {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import {
  api,
  clearAuthSession,
  clearLegacyAuthStorage,
  hasAuthSession,
  RegisterResponse,
  ResendVerificationResponse,
  setAuthFailureHandler,
  User,
} from "@/lib/api";

export interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (
    email: string,
    password: string,
    first_name: string,
    last_name: string
  ) => Promise<RegisterResponse>;
  logout: () => Promise<void>;
  verifyEmail: (token: string) => Promise<void>;
  resendVerification: (email: string) => Promise<ResendVerificationResponse>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    clearLegacyAuthStorage();

    return setAuthFailureHandler(() => {
      setUser(null);
      setIsLoading(false);
      router.replace("/");
    });
  }, [router]);

  useEffect(() => {
    let cancelled = false;

    async function initAuth() {
      try {
        if (hasAuthSession()) {
          const userData = await api.getMe();
          if (!cancelled) {
            setUser(userData);
          }
        }
      } catch (error) {
        console.error("Failed to authenticate the in-memory session", error);
        clearAuthSession();
        if (!cancelled) {
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    initAuth();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const response = await api.login({ email, password });
      setUser(response.user);
    } catch (error) {
      clearAuthSession();
      setUser(null);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const signup = useCallback(async (
    email: string,
    password: string,
    first_name: string,
    last_name: string
  ) => {
    setIsLoading(true);
    try {
      const response = await api.register({
        email,
        password,
        first_name,
        last_name,
      });
      return response;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    setUser(null);
    router.replace("/");
    try {
      await api.logout();
    } catch (error) {
      console.error("Backend logout could not be completed", error);
    }
  }, [router]);

  const verifyEmail = useCallback(async (token: string) => {
    await api.verifyEmail(token);
  }, []);

  const resendVerification = useCallback(async (email: string) => {
    return api.resendVerification(email);
  }, []);

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      isLoading,
      isAuthenticated: !!user,
      login,
      signup,
      logout,
      verifyEmail,
      resendVerification,
    }),
    [user, isLoading, login, signup, logout, verifyEmail, resendVerification],
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}
