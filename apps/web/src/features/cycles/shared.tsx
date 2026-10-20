"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { ApiClientError } from "../../lib/api-client";
import { useAuth } from "../auth/auth-provider";
import type { CycleStatus } from "./api";

export const cycleStatus: Record<CycleStatus, string> = { DRAFT: "Bản nháp", ACTIVE: "Đang đánh giá", CLOSED: "Đã đóng" };
export function ReviewAccess({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return user && ["HR", "MANAGER", "EMPLOYEE"].includes(user.role) ? children : <p role="alert">Bạn không có quyền truy cập đánh giá nhân sự.</p>;
}
const errors: Record<string, string> = {
  stale_version: "Dữ liệu đã được người khác thay đổi. Thông tin đang nhập được giữ lại; hãy tải bản mới rồi kiểm tra trước khi lưu lại.",
  stale_evidence_version: "KPI đã được người khác thay đổi. Thông tin đang nhập được giữ lại; hãy tải bản mới rồi nhập lại thay đổi.",
  active_cycle_exists: "Đã có chu kỳ đang đánh giá. Chỉ được kích hoạt một chu kỳ tại một thời điểm.",
  activation_requirements_not_met: "Chưa thể kích hoạt. Kiểm tra nhân viên, phòng ban, chức danh và tài khoản của nhân viên/người quản lý.",
  participant_already_enrolled: "Có nhân viên đã tham gia chu kỳ. Hãy tải lại danh sách và chọn lại.",
  cycle_not_draft: "Chu kỳ đã kích hoạt, không thể sửa thông tin hoặc danh sách tham gia.",
  cycle_not_active: "Chỉ chỉnh KPI khi chu kỳ đang đánh giá.",
  participant_finalized: "Đánh giá đã chốt, không thể sửa KPI.",
  kpi_definition_inactive: "KPI đã ngừng sử dụng, không thể gán mới.",
  kpi_policy_incompatible: "KPI càng thấp càng tốt cần chu kỳ có giới hạn điểm hữu hạn.",
  duplicate_code: "Mã KPI đã tồn tại.",
  forbidden: "Bạn không có quyền thực hiện thao tác này.",
  validation_error: "Dữ liệu chưa hợp lệ. Kiểm tra ngày, số thập phân và tổng trọng số.",
  reference_inactive: "Có nhân viên hoặc dữ liệu tổ chức đã ngừng hoạt động.",
  cycle_not_found: "Không tìm thấy chu kỳ trong phạm vi truy cập.",
  participant_not_found: "Nhân viên không tham gia chu kỳ hoặc nằm ngoài phạm vi truy cập.",
  employee_kpi_not_found: "KPI không còn tồn tại hoặc nằm ngoài phạm vi truy cập.",
};
export function reviewError(error: Error): string {
  return error instanceof ApiClientError ? errors[error.code] ?? "Không thể thực hiện yêu cầu. Vui lòng tải lại dữ liệu." : "Không thể kết nối. Vui lòng thử lại.";
}
export function ReviewError({ error, reload }: { error: Error; reload?: () => void }) {
  return <div role="alert"><p>{reviewError(error)}</p>
    {error instanceof ApiClientError && error.details.map((item, index) => <p key={index}>
      {typeof item.employee_id === "string" && <><Link href={`/employees/${encodeURIComponent(item.employee_id)}`}>Hồ sơ cần kiểm tra</Link>: </>}
      {typeof item.code === "string" && (issueLabels[item.code] ?? "Kiểm tra lại thông tin.")}
      {typeof item.issue_count === "number" && `Tổng số điều kiện cần xử lý: ${item.issue_count}`}
      {typeof item.location === "string" && <>Trường {item.location}: kiểm tra giá trị nhập.</>}
    </p>)}
    {reload && <button type="button" className="secondary" onClick={reload}>Tải bản mới</button>}
  </div>;
}
const issueLabels: Record<string, string> = {
  participants_required: "Chọn ít nhất một nhân viên.", employee_inactive: "Nhân viên đã ngừng làm việc.",
  department_inactive: "Phòng ban đã ngừng hoạt động.", position_inactive: "Chức danh đã ngừng hoạt động.",
  self_account_required: "Nhân viên cần tài khoản đang hoạt động.", active_manager_required: "Cần người quản lý đang làm việc.",
  manager_account_required: "Người quản lý cần tài khoản đang hoạt động.",
};

// Parse decimal text into an integer in the smallest unit, never adding float percentages.
export function decimalUnits(value: string, scale: number, integerDigits: number): number | null {
  if (!new RegExp(`^\\d{1,${integerDigits}}(?:\\.\\d{1,${scale}})?$`).test(value)) return null;
  const [whole, fraction = ""] = value.split(".");
  const units = Number(whole + fraction.padEnd(scale, "0"));
  return Number.isSafeInteger(units) ? units : null;
}
