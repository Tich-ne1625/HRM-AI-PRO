"use client";

import type { ReactNode } from "react";
import { ApiClientError } from "../../lib/api-client";
import { useAuth } from "../auth/auth-provider";

export function OrganizationAccess({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (!user || !["HR", "MANAGER", "EMPLOYEE"].includes(user.role)) {
    return <p role="alert">Bạn không có quyền truy cập dữ liệu tổ chức.</p>;
  }
  return children;
}

export function organizationError(error: Error | null): string {
  const messages: Record<string, string> = {
    duplicate_code: "Mã này đã tồn tại.", employee_code_already_exists: "Mã nhân viên đã tồn tại.",
    user_already_linked: "Tài khoản đã liên kết với hồ sơ khác.",
    reporting_cycle: "Quan hệ quản lý tạo thành vòng lặp. Hãy chọn người quản lý khác.",
    reference_inactive: "Phòng ban hoặc chức danh đã ngừng hoạt động. Hãy chọn lại.",
    manager_inactive: "Người quản lý đã ngừng làm việc. Hãy chọn lại.",
    user_not_found: "Không tìm thấy tài khoản cần liên kết.",
    employee_not_found: "Không tìm thấy hồ sơ trong phạm vi truy cập.",
    reference_not_found: "Phòng ban hoặc chức danh không còn tồn tại.",
    forbidden: "Bạn không có quyền thực hiện thao tác này.",
    validation_error: "Dữ liệu không hợp lệ. Hãy kiểm tra mã, tên và các lựa chọn.",
  };
  return error instanceof ApiClientError
    ? messages[error.code] ?? "Không thể lưu thay đổi. Vui lòng thử lại."
    : "Không thể kết nối. Vui lòng thử lại.";
}

export function Pagination({ page, total, size = 20, pending, onPage }: {
  page: number; total: number; size?: number; pending: boolean; onPage: (page: number) => void;
}) {
  return <nav className="pagination" aria-label="Phân trang">
    <button type="button" className="secondary" disabled={page <= 1 || pending} onClick={() => onPage(page - 1)}>Trang trước</button>
    <span>Trang {page} · {total} kết quả</span>
    <button type="button" className="secondary" disabled={page * size >= total || pending} onClick={() => onPage(page + 1)}>Trang sau</button>
  </nav>;
}
