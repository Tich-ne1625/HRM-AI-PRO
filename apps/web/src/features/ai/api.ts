import { apiFetch } from "../../lib/api-client";
import type { Page } from "../organization/api";

export type Audience = "PUBLIC" | "HR_PRIVATE";
export interface Output { summary: string; strengths: string[]; improvement_areas: string[]; feedback_themes: string[]; recommended_actions: string[]; caveats: string[] }
export interface Analysis { id: string; audience: Audience; generation_version: number; calculation_version: number; evidence_version: number; status: "RUNNING" | "SUCCEEDED" | "FAILED"; model: string; prompt_version: string; reserved_at: string; generated_at: string | null; error_code: string | null; output: Output | null; input_sampled: boolean; advisory: boolean }
export interface State { audience: Audience; state: string; configured: boolean; can_generate: boolean; can_retry: boolean; current_analysis: Analysis | null; last_successful_analysis: Analysis | null; latest_attempt: Analysis | null }
export interface Intent { client_request_id: string; expected_calculation_version: number; expected_evidence_version: number; audience: Audience; regenerate: boolean; expected_latest_generation?: number }
export interface SavedReport {
  id: string; review_id: string; employee_id: string; display_name: string;
  cycle_id: string; cycle_name: string; audience: Audience; generation_version: number;
  calculation_version: number; model: string; generated_at: string; matches_current_calculation: boolean;
}
export const aiApi = {
  reports: (audience: Audience, cycle: string, page: number) => apiFetch<Page<SavedReport>>(`/api/v1/ai-reports?audience=${audience}&page=${page}${cycle ? `&cycle_id=${encodeURIComponent(cycle)}` : ""}`),
  state: (review: string, audience: Audience) => apiFetch<State>(`/api/v1/performance/${review}/ai-analysis?audience=${audience}`),
  generate: (review: string, intent: Intent) => apiFetch<Analysis>(`/api/v1/performance/${review}/ai-analysis`, { method: "POST", body: JSON.stringify(intent) }, { skipRefresh: true }),
  history: (review: string, audience: Audience, page: number) => apiFetch<Page<Analysis>>(`/api/v1/reviews/${review}/ai-analyses?audience=${audience}&page=${page}`),
  detail: (review: string, id: string) => apiFetch<Analysis>(`/api/v1/reviews/${review}/ai-analyses/${id}`),
};
