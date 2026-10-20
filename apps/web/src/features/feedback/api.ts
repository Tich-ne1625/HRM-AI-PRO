import { apiFetch } from "../../lib/api-client";
import type { CycleStatus, Filters } from "../cycles/api";
import type { Page } from "../organization/api";

export type Relationship = "SELF" | "MANAGER" | "PEER" | "SUBORDINATE";
export type Status = "OPEN" | "SUBMITTED" | "CANCELLED";
export interface Submission { rating: number; comment: string; submitted_at: string }
export interface Assignment {
  id: string; participant_id: string; cycle_id: string; cycle_name: string; cycle_status: CycleStatus;
  start_date: string; end_date: string; employee_id: string; employee_code: string; display_name: string;
  relationship: Relationship; required: boolean; status: Status; due_at: string | null;
  version: number; evidence_version: number; finalized: boolean; submission: Submission | null;
}
export interface Administration extends Assignment {
  reviewer_id: string; reviewer_employee_id: string; reviewer_name: string; reviewer_active: boolean;
}
export interface ReviewerOption {
  reviewer_id: string; employee_id: string; employee_code: string; display_name: string;
  is_active: boolean; existing_assignment_id: string | null; existing_status: Status | null;
}
export interface Coverage { ready: boolean; missing_relationships: Relationship[]; pending_required: number; blocked_required: number; pending_assignment_ids: string[]; blocked_assignment_ids: string[] }
export interface AdministrationContext { participant_id: string; cycle_id: string; employee_id: string; employee_code: string; display_name: string; evidence_version: number; cycle_status: CycleStatus; finalized: boolean; coverage: Coverage }
export interface Summary {
  participant_id: string; employee_id: string; cycle_id: string; evidence_version: number; ready: boolean;
  count: number; mean: string | null; own_submission: Submission | null;
  groups: { relationship: Relationship; suppressed: boolean; count: number | null; mean: string | null }[];
}
export interface Versions { expected_assignment_version: number; expected_evidence_version: number }
export interface FeedbackInput extends Versions { assignment_id: string; rating: number; comment: string }
export type Reason = "WRONG_SELECTION" | "REVIEWER_UNAVAILABLE" | "NO_LONGER_REQUIRED";
const query = (filters: Filters) => new URLSearchParams(Object.entries(filters)
  .filter(([, value]) => value !== undefined && value !== "").map(([key, value]) => [key, String(value)])).toString();
const write = <T>(path: string, method: string, body: unknown) => apiFetch<T>(path, { method, body: JSON.stringify(body) });
const base = "/api/v1/feedback-assignments";
export const feedbackApi = {
  list: (filters: Filters) => apiFetch<Page<Assignment>>(`${base}?${query(filters)}`),
  administration: (filters: Filters) => apiFetch<Page<Administration>>(`${base}?${query({ ...filters, view: "administration" })}`),
  detail: (id: string) => apiFetch<Assignment>(`${base}/${id}`),
  adminDetail: (id: string) => apiFetch<Administration>(`${base}/${id}`),
  context: (participant: string) => apiFetch<AdministrationContext>(`/api/v1/feedback-context?participant_id=${encodeURIComponent(participant)}`),
  options: (participant: string, relationship: Relationship, filters: Filters = {}) => apiFetch<Page<ReviewerOption>>(`/api/v1/feedback-reviewer-options?${query({ ...filters, participant_id: participant, relationship })}`),
  coverage: (participant: string) => apiFetch<Coverage>(`/api/v1/feedback-coverage?participant_id=${encodeURIComponent(participant)}`),
  create: (body: { participant_id: string; reviewer_id: string; relationship: Relationship; required: boolean; due_at: string | null; expected_evidence_version: number }) => write<Administration>(base, "POST", body),
  update: (id: string, body: Versions & { required?: boolean; due_at?: string | null; status?: "OPEN" }) => write<Administration>(`${base}/${id}`, "PATCH", body),
  cancel: (id: string, body: Versions & { reason_code: Reason }) => write<Administration>(`${base}/${id}`, "DELETE", body),
  replace: (id: string, body: Versions & { reviewer_id: string; due_at: string | null; reason_code: Reason }) => write<Administration>(`${base}/${id}/replace`, "POST", body),
  submit: (body: FeedbackInput) => write<Assignment>("/api/v1/feedback", "POST", body),
  summary: (employee: string, cycle: string) => apiFetch<Summary>(`/api/v1/employees/${employee}/feedback?cycle_id=${encodeURIComponent(cycle)}`),
};
