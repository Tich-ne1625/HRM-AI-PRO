import { apiFetch } from "../../lib/api-client";
import type { CycleStatus, Policy } from "../cycles/api";
import type { Summary } from "../feedback/api";
import type { Page } from "../organization/api";

export interface Readiness { ready: boolean; issue_count: number; issues: { code: string; kpi_id: string | null }[] }
export interface ScoreLine { id: string; code: string; name: string; unit: string; direction: string; target: string; actual: string; weight: string; raw_score: string; normalized_score: string; weighted_score: string }
export interface Calculation {
  calculation_version: number; evidence_version: number; engine_version: string; calculated_at: string;
  kpi_score: string; feedback_score: string; final_score: string; policy: Policy; items: ScoreLine[];
  feedback: Pick<Summary, "count" | "mean" | "groups" | "own_submission">;
}
export interface Report {
  review_id: string | null; participant_id: string; employee_id: string; employee_code: string; display_name: string;
  cycle_id: string; cycle_name: string; cycle_status: CycleStatus; cycle_version: number; evidence_version: number;
  state: "NOT_CALCULATED" | "CURRENT" | "STALE" | "FINALIZED";
  current_result: Calculation | null; last_calculation: Calculation | null; readiness: Readiness;
  can_calculate: boolean; can_finalize: boolean; finalized_at: string | null; reused: boolean;
}
export interface FinalizationContext { review_id: string; evidence_version: number; calculation_version: number; readiness: Readiness; open_optional_count: number }
export type Revision = Pick<Calculation, "calculation_version" | "evidence_version" | "calculated_at" | "kpi_score" | "feedback_score" | "final_score">;
const write = <T>(path: string, body: unknown) => apiFetch<T>(path, { method: "POST", body: JSON.stringify(body) });
export const performanceApi = {
  report: (employee: string, cycle: string) => apiFetch<Report>(`/api/v1/performance/${employee}?cycle_id=${encodeURIComponent(cycle)}`),
  calculate: (employee: string, cycle: string, version: number) => write<Report>(`/api/v1/performance/${employee}/calculate`, { cycle_id: cycle, expected_evidence_version: version }),
  context: (review: string) => apiFetch<FinalizationContext>(`/api/v1/reviews/${review}/finalization-context`),
  finalize: (review: string, context: FinalizationContext) => write<Report>(`/api/v1/reviews/${review}/finalize`, { expected_evidence_version: context.evidence_version, expected_calculation_version: context.calculation_version, acknowledge_open_optional_count: context.open_optional_count }),
  revisions: (review: string, page: number) => apiFetch<Page<Revision>>(`/api/v1/reviews/${review}/revisions?page=${page}`),
  revision: (review: string, version: number) => apiFetch<Calculation>(`/api/v1/reviews/${review}/revisions/${version}`),
  close: (cycle: string, version: number) => write<{ id: string; status: "CLOSED"; version: number }>(`/api/v1/review-cycles/${cycle}/close`, { expected_version: version }),
};
