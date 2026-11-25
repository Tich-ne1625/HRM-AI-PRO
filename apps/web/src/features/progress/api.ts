import { apiFetch } from "../../lib/api-client";
import type { Page } from "../organization/api";
import type { Goal } from "../work-management/api";

export interface Metric {
  goal_id: string; name: string; method: Goal["method"]; unit: string; target: string;
  actual: string | null; data_status: string; source_count: number; pending_count: number;
  specification: Goal;
}
export interface Metrics {
  plan_id: string; plan_version: number; measurement_version: number; employee_name: string;
  owner_id: string; manager_id: string | null; can_submit: boolean; goals: Metric[];
  start_date?: string; end_date?: string; can_schedule?: boolean;
}
export interface Measurement {
  id: string; plan_id: string; goal_id: string; version: number; number: number;
  source_key: string; source_kind: string; work_item_id: string | null; occurred_at: string;
  milestone: number | null; status: string; suspended: boolean; kind: "VALUE" | "VOID";
  payload: Record<string, string | number | null>; method: Goal["method"]; actions: string[];
  effective: {number: number; kind: string; payload: Record<string, string | number | null>} | null;
  is_correction: boolean;
  input_closed?: boolean; next_actor?: string;
  revisions?: {id: string; number: number; kind: string; payload: Record<string, string | number | null>; created_at: string}[];
  history?: Page<Event>;
  selected_revision?: {number: number; kind: "VALUE" | "VOID"; payload: Record<string, string | number | null>; created_at: string} | null;
}
export interface Event { id: string; kind: string; body: string; created_at: string; actor_id: string }
export interface Followup {
  id: string; version: number; body: string; owner_id: string; reviewer_id: string;
  due_at: string; status: string; actions: string[]; overdue: boolean;
}
export interface Checkin {
  id: string; plan_id: string; version: number; title: string; scheduled_at: string;
  period_start: string; period_end: string; status: string; publication: number;
  acknowledged_publication: number | null; clarification_pending: boolean;
  owner_id: string; manager_id: string | null; verification_due_at: string;
  snapshot_id: string | null; overdue: boolean; can_prepare: boolean; actions: string[];
  actions_open?: boolean;
  preparations?: {author_id: string; body: string; shared: boolean; version: number}[];
  publications?: {number: number; body: string; created_at: string; preparations: {author_id: string; body: string}[]}[];
  snapshot?: {id: string; version: number; known_at: string; goals: Metric[]} | null;
  followups?: Page<Followup>; history?: Page<Event>;
}
export interface Snapshot {
  id: string; version: number; known_at: string; content_hash: string; goals: Metric[];
  sources: Page<{measurement_id: string; number: number; source_key: string; occurred_at: string; payload: Record<string, string | number | null>}>;
}
export const progressApi = {
  metrics: (id: string, from?: string, to?: string) => apiFetch<Metrics>(`/api/v1/progress/plans/${id}/goals${from && to ? `?from_date=${from}&to_date=${to}` : ""}`),
  measurements: (goal: string, page: number) => apiFetch<Page<Measurement>>(`/api/v1/progress/goals/${goal}/measurements?page=${page}`),
  measurement: (id: string, page = 1, revision?: number) => apiFetch<Measurement>(`/api/v1/progress/measurements/${id}?page=${page}${revision !== undefined ? `&revision_number=${revision}` : ""}`),
  checkins: (plan: string, page: number) => apiFetch<Page<Checkin>>(`/api/v1/checkins?plan_id=${plan}&page=${page}`),
  checkin: (id: string, page = 1) => apiFetch<Checkin>(`/api/v1/checkins/${id}?page=${page}`),
  snapshot: (id: string, page = 1) => apiFetch<Snapshot>(`/api/v1/progress/snapshots/${id}?page=${page}`),
  snapshots: (plan: string, page: number) => apiFetch<Page<{id: string; version: number; created_at: string}>>(`/api/v1/progress/plans/${plan}/snapshots?page=${page}`),
  coordination: (plan: string) => apiFetch<{employee_name: string; measurements: Record<string, number>; checkins: Record<string, number>; actions: Record<string, number>; overdue: Record<string, number>; needs_hr: boolean}>(`/api/v1/progress/plans/${plan}/coordination`),
  write: <T>(path: string, body: unknown) => apiFetch<T>(`/api/v1/${path}`, {method: "POST", body: JSON.stringify(body)}),
};
