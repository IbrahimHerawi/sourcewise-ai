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
  clearStoredAuthToken,
  getStoredAuthToken,
  RegisterResponse,
  ResendVerificationResponse,
  storeAuthToken,
  User,
} from "@/lib/api";

export interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (
    email: string,
    password: string,
    first_name: string,
    last_name: string
  ) => Promise<RegisterResponse>;
  logout: () => void;
  verifyEmail: (token: string) => Promise<void>;
  resendVerification: (email: string) => Promise<ResendVerificationResponse>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    async function initAuth() {
      const savedToken = getStoredAuthToken();

      try {
        if (savedToken) {
          setToken(savedToken);
          const userData = await api.getMe();
          setUser(userData);
        }
      } catch (error) {
        console.error("Failed to authenticate with saved token", error);
        clearStoredAuthToken();
        setToken(null);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    }

    initAuth();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const response = await api.login({ email, password });
      storeAuthToken(response.access_token);
      setToken(response.access_token);
      setUser(response.user);
    } catch (error) {
      clearStoredAuthToken();
      setToken(null);
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

  const logout = useCallback(() => {
    clearStoredAuthToken();
    setToken(null);
    setUser(null);
    router.replace("/");
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
      token,
      isLoading,
      isAuthenticated: !!user,
      login,
      signup,
      logout,
      verifyEmail,
      resendVerification,
    }),
    [user, token, isLoading, login, signup, logout, verifyEmail, resendVerification],
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}
