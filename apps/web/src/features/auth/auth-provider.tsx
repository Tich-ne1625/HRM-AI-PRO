"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, type ReactNode } from "react";

import { ApiClientError, resetApiSession } from "../../lib/api-client";
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
  return useMutation({ mutationFn: authApi.login, onMutate: () => { resetApiSession(); }, onSuccess: (user) => {
    resetApiSession();
    cache.clear();
    cache.setQueryData(["auth", "me"], user);
  } });
}

function useLogout() {
  const cache = useQueryClient();
  return useMutation({ mutationFn: authApi.logout, onMutate: () => { resetApiSession(); }, onSuccess: () => {
    resetApiSession();
    cache.clear();
    cache.setQueryData(["auth", "me"], null);
  } });
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const cache = useQueryClient();
  useEffect(() => {
    const recheck = () => { void cache.invalidateQueries({ queryKey: ["auth", "me"] }); };
    window.addEventListener("insighthr-authority-recheck", recheck);
    return () => window.removeEventListener("insighthr-authority-recheck", recheck);
  }, [cache]);
  const query = useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      let next: CurrentUser | null;
      try { next = await authApi.me(); }
      catch (error) {
        if (error instanceof ApiClientError && error.status === 401) next = null;
        else throw error;
      }
      const previous = cache.getQueryData<CurrentUser | null>(["auth", "me"]);
      const identity = (value: CurrentUser | null) => value ? `${value.id}:${value.role}:${value.employee_id}` : "anonymous";
      if (previous !== undefined && identity(previous) !== identity(next)) {
        resetApiSession();
        const filter = { predicate: (item: { queryKey: readonly unknown[] }) => item.queryKey[0] !== "auth" };
        await cache.cancelQueries(filter); cache.removeQueries(filter);
      }
      return next;
    }, retry: false, staleTime: 30_000,
  });
  const login = useLogin();
  const logout = useLogout();
  return <AuthContext.Provider key={`${query.data?.id}:${query.data?.role}:${query.data?.employee_id}`} value={{
    user: query.data ?? null, pending: query.isPending, error: query.error,
    retry: () => { void query.refetch(); }, login, logout,
  }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth requires AuthProvider");
  return value;
}
