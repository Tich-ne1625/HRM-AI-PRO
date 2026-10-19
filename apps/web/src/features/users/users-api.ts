import { apiFetch } from "../../lib/api-client";
import type { CurrentUser, UserRole } from "../auth/types";

export interface CreateUserInput { email: string; password: string; role: UserRole }
export interface UserPage { items: CurrentUser[]; total: number; page: number; page_size: number }
export const usersApi = {
  list: (page: number) => apiFetch<UserPage>(`/api/v1/users?page=${page}&page_size=20`),
  create: (input: CreateUserInput) => apiFetch<CurrentUser>("/api/v1/users", {
    method: "POST", body: JSON.stringify(input),
  }),
  update: (id: string, input: { role?: UserRole; is_active?: boolean }) => apiFetch<CurrentUser>(`/api/v1/users/${id}`, {
    method: "PATCH", body: JSON.stringify(input),
  }),
};
