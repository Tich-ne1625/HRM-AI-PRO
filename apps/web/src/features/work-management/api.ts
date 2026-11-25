import { apiFetch } from "../../lib/api-client";
import type { Page } from "../organization/api";
import type { Definition } from "../cycles/api";

export type WorkStatus = "PROPOSED" | "TODO" | "IN_PROGRESS" | "SUBMITTED" | "CHANGES_REQUESTED" | "ACCEPTED" | "CANCELLED";
export const statusLabel: Record<string, string> = {
  DRAFT: "Đang soạn", SUBMITTED: "Đã gửi · chờ duyệt", CHANGES_REQUESTED: "Cần bổ sung",
  APPROVED: "Kế hoạch đã duyệt", PROPOSED: "Đề xuất chờ duyệt", TODO: "Chưa bắt đầu",
  IN_PROGRESS: "Đang thực hiện", ACCEPTED: "Đã nghiệm thu", CANCELLED: "Đã hủy",
};
export const actionLabel: Record<string, string> = {
  submit: "Gửi để duyệt", approve: "Duyệt kế hoạch", clarify: "Yêu cầu làm rõ",
  acknowledge: "Xác nhận đã nhận kế hoạch", comment: "Gửi trao đổi", publish: "Duyệt và giao việc",
  start: "Bắt đầu thực hiện", update: "Cập nhật tiến trình", block: "Báo vướng mắc",
  unblock: "Đã gỡ vướng", accept: "Nghiệm thu", return: "Yêu cầu bổ sung",
  cancel: "Hủy công việc", reopen: "Mở lại để bổ sung", request_change: "Đề nghị thay đổi",
};
export interface WorkParticipant {
  participant_id: string; employee_name: string; cycle_id: string; cycle_name: string;
  cycle_status: string; plan_id: string | null; plan_status: string | null;
  acknowledged: boolean; can_draft: boolean; needs_hr: boolean;
}
export interface Goal {
  id: string; definition_id: string; baseline: string; target: string; weight: string;
  method: "SUM" | "LAST" | "RATIO" | "MILESTONE"; source: string; acceptance: string;
  numerator: string | null; denominator: string | null;
  milestones: { title: string; weight: string }[];
  definition: { code: string; name: string; direction: string; unit: string };
}
export interface Plan {
  id: string; participant_id: string; version: number; revision: number; status: string;
  acknowledged_revision: number | null; objective: string; employee_name: string;
  cycle_id: string; cycle_name: string; cycle_status: string; start_date: string; end_date: string;
  goals: Goal[]; actions: string[]; can_create_work: boolean; is_manager: boolean; needs_hr: boolean;
  schedule: Record<string, string>;
}
export interface Work {
  id: string; plan_id: string; version: number; title: string; acceptance: string;
  priority: string; source_key: string; due_at: string; status: WorkStatus; goal_id: string | null;
  blocked: boolean; blocked_reason: string; employee_name: string; cycle_name: string;
  actions: string[]; needs_hr: boolean; next_actor: string;
  submissions?: { id: string; number: number; body: string; url: string | null; created_at: string }[];
  submission_total?: number;
}
export interface WorkEvent { id: string; kind: string; body: string; actor: string; revision: number; created_at: string }
const base = "/api/v1/work-management";
const params = (values: Record<string, string | number | undefined>) => new URLSearchParams(
  Object.entries(values).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]));
export const workApi = {
  participants: (page: number, cycle?: string) => apiFetch<Page<WorkParticipant>>(`${base}/participants?${params({page, cycle_id: cycle})}`),
  definitions: (page: number, q: string) => apiFetch<Page<Definition>>(`${base}/definitions?${params({page, q})}`),
  plan: (id: string) => apiFetch<Plan>(`${base}/plans/${id}`),
  items: (page: number, status: string, blocked: string, plan?: string) => apiFetch<Page<Work>>(`${base}/items?${params({page, status, blocked, plan_id: plan})}`),
  item: (id: string, page = 1) => apiFetch<Work>(`${base}/items/${id}?page=${page}`),
  history: (id: string, page: number, work?: string) => apiFetch<Page<WorkEvent>>(`${base}/plans/${id}/history?${params({page, work_id: work})}`),
  revisions: (id: string, page: number) => apiFetch<Page<{number: number; objective: string; created_at: string; goals: Omit<Goal, "id">[]}>>(`${base}/plans/${id}/revisions?page=${page}`),
  write: <T>(path: string, body: unknown) => apiFetch<T>(`${base}/${path}`, {method: "POST", body: JSON.stringify(body)}),
};
