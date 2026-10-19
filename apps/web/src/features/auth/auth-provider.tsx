"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, type ReactNode } from "react";

import { ApiClientError } from "../../lib/api-client";
import { authApi } from "./api";
import type { CurrentUser } from "./types";

interface AuthState {
  user: CurrentUser | null;
  pending: boolean;
  error: Error | null;
  retry: () => void;
  login: ReturnType<typeof useLogin>;
  logout: ReturnType<typeof useLogout>;
}

function useLogin() {
  const cache = useQueryClient();
  return useMutation({ mutationFn: authApi.login, onSuccess: (user) => {
    cache.clear();
    cache.setQueryData(["auth", "me"], user);
  } });
}

function useLogout() {
  const cache = useQueryClient();
  return useMutation({ mutationFn: authApi.logout, onSuccess: () => {
    cache.clear();
    cache.setQueryData(["auth", "me"], null);
  } });
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const query = useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      try { return await authApi.me(); }
      catch (error) {
        if (error instanceof ApiClientError && error.status === 401) return null;
        throw error;
      }
    }, retry: false, staleTime: 30_000,
  });
  const login = useLogin();
  const logout = useLogout();
  return <AuthContext.Provider value={{
    user: query.data ?? null, pending: query.isPending, error: query.error,
    retry: () => { void query.refetch(); }, login, logout,
  }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth requires AuthProvider");
  return value;
}
