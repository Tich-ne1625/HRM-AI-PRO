import { apiFetch } from "../../lib/api-client";

export type ReferenceKind = "departments" | "positions";
export interface Reference {
  id: string; code: string; name?: string; title?: string; is_active: boolean;
  created_at: string; updated_at: string;
}
export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
export interface Employee {
  id: string; employee_code: string; display_name: string;
  department_id: string; department_name: string; position_id: string; position_title: string;
  manager_id: string | null; manager_name: string | null; user_id: string | null;
  employment_status: "ACTIVE" | "INACTIVE"; created_at: string; updated_at: string;
}
export interface EmployeeInput {
  employee_code: string; display_name: string; department_id: string; position_id: string;
  manager_id: string | null; user_id: string | null; employment_status: "ACTIVE" | "INACTIVE";
}
export interface AccountMatch { id: string; email: string; is_active: boolean; employee_id: string | null }
export interface ReferenceInput { code?: string; name?: string; title?: string; is_active?: boolean }
export interface Filters {
  page?: number; page_size?: number; q?: string; is_active?: boolean;
  department_id?: string; position_id?: string; employment_status?: string;
}
function query(filters: Filters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  return params.toString();
}
export const referenceLabel = (row: Reference) => row.name ?? row.title ?? row.code;
export const organizationApi = {
  references: (kind: ReferenceKind, filters: Filters = {}) => apiFetch<Page<Reference>>(`/api/v1/${kind}?${query(filters)}`),
  saveReference: (kind: ReferenceKind, id: string | null, input: ReferenceInput) => apiFetch<Reference>(`/api/v1/${kind}${id ? `/${id}` : ""}`, {
    method: id ? "PATCH" : "POST", body: JSON.stringify(input),
  }),
  employees: (filters: Filters = {}) => apiFetch<Page<Employee>>(`/api/v1/employees?${query(filters)}`),
  employee: (id: string) => apiFetch<Employee>(`/api/v1/employees/${id}`),
  saveEmployee: (id: string | null, input: Partial<EmployeeInput>) => apiFetch<Employee>(`/api/v1/employees${id ? `/${id}` : ""}`, {
    method: id ? "PATCH" : "POST", body: JSON.stringify(input),
  }),
  lookup: (email: string) => apiFetch<{ items: AccountMatch[] }>(`/api/v1/employees/linkable-users?email=${encodeURIComponent(email)}`),
};
