import { apiFetch } from "../../lib/api-client";

export type Notice = { id: string; title: string; message: string; href: string; created_at: string; read_at: string | null };
export type NoticePage = { items: Notice[]; total: number; unread_count: number; page: number; page_size: number };
export type Task = { id: string; title: string; detail: string; href: string; waiting: boolean };
export const notificationApi = {
  list: (page: number, unread: boolean) => apiFetch<NoticePage>(`/api/v1/notifications?page=${page}&unread=${unread}`),
  tasks: () => apiFetch<{ items: Task[]; truncated: boolean }>("/api/v1/notifications/tasks"),
  read: (id: string) => apiFetch(`/api/v1/notifications/${id}/read`, { method: "POST" }),
  readAll: () => apiFetch("/api/v1/notifications/read-all", { method: "POST" }),
};
