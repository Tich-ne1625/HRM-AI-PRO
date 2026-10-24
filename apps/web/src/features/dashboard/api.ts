import { apiFetch } from "../../lib/api-client";

export interface CycleOption { id: string; name: string; status: string }
export interface Activity { id: string; action: string; occurred_at: string; employee_id: string | null; display_name: string | null; cycle_id: string | null }
export interface Overview {
  role: string; pending_feedback: number;
  recent_activities?: Activity[];
  active_accounts?: number; inactive_accounts?: number; account_roles?: Record<string, number>;
  active_employees?: number; cycles?: CycleOption[]; cycles_truncated?: boolean;
  selected_cycle?: CycleOption | null; participants?: number; finalized?: number;
  current?: number; stale?: number; not_calculated?: number; awaiting_completion?: number;
  sample_size?: number; average?: string | null; score_bands?: Record<string, number>;
  kpis_assigned?: number; kpis_entered?: number; kpi_entry_percent?: string | null;
  departments?: { id: string; name: string; participants: number; sample_size: number; average: string | null }[];
  departments_truncated?: boolean;
}
export const dashboardApi = {
  get: (cycle: string) => apiFetch<Overview>(`/api/v1/dashboard${cycle ? `?cycle_id=${encodeURIComponent(cycle)}` : ""}`),
};
