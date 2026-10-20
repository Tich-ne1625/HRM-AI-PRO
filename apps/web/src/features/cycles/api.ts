import { apiFetch } from "../../lib/api-client";
import type { Page } from "../organization/api";

export type CycleStatus = "DRAFT" | "ACTIVE" | "CLOSED";
export type Direction = "HIGHER_IS_BETTER" | "LOWER_IS_BETTER";
export interface Policy { schema_version: 1; kpi_weight: string; feedback_weight: string; kpi_cap: string | null }
export interface ScoringDefaults { version: number; policy: Policy }
export interface Cycle {
  id: string; name: string; start_date: string; end_date: string; status: CycleStatus;
  version: number; policy: Policy; policy_source_version: number; policy_is_preview: boolean;
  participant_count: number; can_edit: boolean; can_activate: boolean; activated_at: string | null;
}
export interface Participant {
  id: string; cycle_id: string; employee_id: string; employee_code: string; display_name: string;
  department_id: string; department_name: string; position_title: string; evidence_version: number;
  is_snapshot: boolean; can_manage_kpis: boolean;
}
export interface DefinitionInput { code: string; name: string; description: string; unit: string; direction: Direction }
export interface Definition extends DefinitionInput { id: string; is_active: boolean; version: number }
export interface DefinitionSnapshot extends DefinitionInput { schema_version: 1; version: number }
export interface AllocationLine { id: string; definition_id: string; definition: DefinitionSnapshot; target: string; weight: string; actual: string | null }
export interface Allocation { participant: Participant; cycle_status: CycleStatus; items: AllocationLine[] }
export interface AllocationInput { definition_id: string; target: string; weight: string }
export type Filters = Record<string, string | number | boolean | undefined>;
const query = (filters: Filters) => new URLSearchParams(Object.entries(filters)
  .filter(([, value]) => value !== undefined && value !== "").map(([key, value]) => [key, String(value)])).toString();
const write = <T>(path: string, method: string, body: unknown) => apiFetch<T>(path, { method, body: JSON.stringify(body) });
const employeePath = (id: string, cycle: string, kind = "kpis") => `/api/v1/employees/${id}/${kind}?cycle_id=${encodeURIComponent(cycle)}`;
export const reviewApi = {
  cycles: (filters: Filters = {}) => apiFetch<Page<Cycle>>(`/api/v1/review-cycles?${query(filters)}`),
  cycle: (id: string) => apiFetch<Cycle>(`/api/v1/review-cycles/${id}`),
  saveCycle: (id: string | null, body: { name: string; start_date: string; end_date: string; expected_version?: number }) => write<Cycle>(`/api/v1/review-cycles${id ? `/${id}` : ""}`, id ? "PATCH" : "POST", body),
  participants: (id: string, filters: Filters = {}) => apiFetch<Page<Participant>>(`/api/v1/review-cycles/${id}/participants?${query(filters)}`),
  enroll: (id: string, version: number, employee_ids: string[]) => write<{version: number; count: number}>(`/api/v1/review-cycles/${id}/participants`, "POST", { expected_version: version, employee_ids }),
  remove: (id: string, participant: string, version: number) => write<{version: number; count: number}>(`/api/v1/review-cycles/${id}/participants/${participant}`, "DELETE", { expected_version: version }),
  activate: (id: string, version: number) => write<Cycle>(`/api/v1/review-cycles/${id}/activate`, "POST", { expected_version: version }),
  definitions: (filters: Filters = {}) => apiFetch<Page<Definition>>(`/api/v1/kpis?${query(filters)}`),
  saveDefinition: (id: string | null, body: Partial<DefinitionInput> & { expected_version?: number; is_active?: boolean }) => write<Definition>(`/api/v1/kpis${id ? `/${id}` : ""}`, id ? "PATCH" : "POST", body),
  options: (id: string, cycle: string, filters: Filters = {}) => apiFetch<Page<Definition>>(`${employeePath(id, cycle, "kpi-options")}&${query(filters)}`),
  allocation: (id: string, cycle: string) => apiFetch<Allocation>(employeePath(id, cycle)),
  replace: (id: string, cycle: string, version: number, items: AllocationInput[]) => write<Allocation>(employeePath(id, cycle), "PUT", { expected_evidence_version: version, items }),
  actual: (id: string, version: number, actual: string | null) => write<Allocation>(`/api/v1/employee-kpis/${id}`, "PATCH", { expected_evidence_version: version, actual }),
  defaults: () => apiFetch<ScoringDefaults>("/api/v1/settings/scoring"),
  saveDefaults: (version: number, policy: Policy) => write<ScoringDefaults>("/api/v1/settings/scoring", "PATCH", { expected_version: version, policy }),
};
