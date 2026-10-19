import { apiFetch } from "../../lib/api-client";
import type { ChangePasswordInput, CurrentUser, LoginInput } from "./types";

export const authApi = {
  me: () => apiFetch<CurrentUser>("/api/v1/auth/me"),
  login: (input: LoginInput) => apiFetch<CurrentUser>("/api/v1/auth/login", {
    method: "POST", body: JSON.stringify(input),
  }),
  logout: () => apiFetch("/api/v1/auth/logout", { method: "POST" }),
  changePassword: (input: ChangePasswordInput) => apiFetch("/api/v1/auth/change-password", {
    method: "POST", body: JSON.stringify(input),
  }, { skipRefresh: true }),
};
