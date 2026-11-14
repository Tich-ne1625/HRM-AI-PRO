import { apiFetch } from "../../lib/api-client";
import type { UserRole } from "../auth/types";

export type Person = { id: string; name: string; role: UserRole; department: string | null; department_id: string | null };
export type Post = { id: string; title: string; body: string; author: Person; mentions: Person[]; department_id: string | null; department: string | null; created_at: string };
export type Comment = { id: string; body: string; author: Person; mentions: Person[]; created_at: string };
export type Message = { id: string; sender_id: string; recipient_id: string; body: string; created_at: string; read_at: string | null };
export type Content = { id: string; body: string; mentions: string[] };
const root = "/api/v1/collaboration";
export const collaborationApi = {
  people: (search: string, page = 1, post?: string, ownDepartment = false, departmentId?: string) => apiFetch<{ items: Person[]; has_more: boolean }>(`${root}/people?${new URLSearchParams({ search, page: String(page), ...(post ? { post_id: post } : {}), ...(departmentId ? { department_id: departmentId } : {}), own_department: String(ownDepartment) })}`),
  feed: (page: number, audience: string) => apiFetch<{ items: Post[]; has_more: boolean; department_id: string | null; can_publish_company: boolean; departments: { id: string; name: string }[] }>(`${root}/posts?page=${page}&audience=${audience}`),
  post: (id: string, page = 1) => apiFetch<{ post: Post; comments: Comment[]; has_more: boolean }>(`${root}/posts/${id}?page=${page}`),
  publish: (data: Content & { title: string; department_id: string | null }) => apiFetch<Post>(`${root}/posts`, { method: "POST", body: JSON.stringify(data) }),
  comment: (id: string, data: Content) => apiFetch<Comment>(`${root}/posts/${id}/comments`, { method: "POST", body: JSON.stringify(data) }),
  conversations: (page: number) => apiFetch<{ items: { peer: Person; latest: Message }[]; has_more: boolean; unread_count: number }>(`${root}/conversations?page=${page}`),
  messages: (peer: string, before?: string) => apiFetch<{ items: Message[]; has_more: boolean }>(`${root}/chat/${peer}${before ? `?before=${before}` : ""}`),
  message: (id: string) => apiFetch<Message>(`${root}/messages/${id}`),
  send: (peer: string, data: Content) => apiFetch<Message>(`${root}/chat/${peer}`, { method: "POST", body: JSON.stringify(data) }),
  read: (peer: string, through: string) => apiFetch(`${root}/chat/${peer}/read`, { method: "POST", body: JSON.stringify({ through_id: through }) }),
};

export function dateTime(value: string) { return new Date(value).toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }); }
