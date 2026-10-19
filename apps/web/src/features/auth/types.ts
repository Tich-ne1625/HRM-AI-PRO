export type UserRole = "ADMIN" | "HR" | "MANAGER" | "EMPLOYEE";

export interface CurrentUser {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  employee_id: string | null;
}

export interface LoginInput { email: string; password: string }
export interface ChangePasswordInput { old_password: string; new_password: string }
