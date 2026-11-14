import type { UserRole } from "../auth/types";

export type NavigationGroup = { label: string; href: string; items: { href: string; label: string }[] };

export function navigationGroups(role: UserRole): NavigationGroup[] {
  const groups: NavigationGroup[] = [{ label: "Tổng quan", href: "/dashboard", items: [{ href: "/dashboard", label: "Tổng quan" }] }];
  groups[0]!.items.push({ href: "/news", label: "Bảng tin nội bộ" });
  if (role !== "ADMIN") groups.push({ label: "Đánh giá hiệu suất", href: "/review-cycles", items: [
    { href: "/review-cycles", label: "Chu kỳ đánh giá" },
    ...(role === "HR" ? [{ href: "/feedback-administration", label: "Phân công phản hồi" }, { href: "/kpis", label: "Danh mục KPI" }] : []),
    { href: "/ai-reports", label: "Tư vấn AI đã lưu" },
  ] });
  if (role === "HR" || role === "MANAGER") groups.push({ label: role === "HR" ? "Tổ chức" : "Nhóm của tôi", href: "/employees", items: [
    { href: "/employees", label: role === "HR" ? "Nhân viên" : "Nhân viên trực tiếp" },
    ...(role === "HR" ? [{ href: "/departments", label: "Phòng ban" }, { href: "/positions", label: "Chức danh" }] : []),
  ] });
  if (role === "ADMIN") groups.push({ label: "Quản trị hệ thống", href: "/admin/users", items: [
    { href: "/admin/users", label: "Quản lý tài khoản" }, { href: "/settings/scoring", label: "Cấu hình chấm điểm" },
  ] });
  groups.push({ label: "Cá nhân", href: "/account", items: [{ href: "/feedback", label: "Phản hồi của tôi" }, { href: "/account", label: "Tài khoản" }] });
  return groups;
}

export function navigationPath(path: string): string {
  if (/^\/employees\/[^/]+\/(kpis|feedback|performance)$/.test(path)) return "/review-cycles";
  return path;
}

export function workspaceRouteAllowed(role: UserRole, path: string): boolean {
  if (/^\/(admin|settings)(\/|$)/.test(path)) return role === "ADMIN";
  if (/^\/(departments|positions|kpis|feedback-administration)(\/|$)/.test(path)) return role === "HR";
  if (path === "/employees") return role === "HR" || role === "MANAGER";
  if (/^\/(employees|review-cycles|ai-reports)(\/|$)/.test(path)) return role !== "ADMIN";
  return path === "/news" || path === "/dashboard" || path === "/account" || /^\/feedback(\/|$)/.test(path);
}
