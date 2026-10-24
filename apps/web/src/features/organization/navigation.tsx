"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAuth } from "../auth/auth-provider";

export function WorkspaceHeader() {
  const { user } = useAuth();
  const path = usePathname() ?? "";
  const domain = user && ["HR", "MANAGER", "EMPLOYEE"].includes(user.role);
  const tabs = [
    { href: "/dashboard", label: "Tổng quan", active: path === "/dashboard" },
    { href: "/account", label: "Cá nhân", active: path === "/account" || path.startsWith("/feedback") && !path.startsWith("/feedback-administration") },
    ...(domain ? [
      { href: "/review-cycles", label: "Đánh giá hiệu suất", active: path.startsWith("/ai-reports") || path.startsWith("/review-cycles") || path.startsWith("/kpis") || path.startsWith("/feedback-administration") || /^\/employees\/[^/]+\/(kpis|feedback|performance)/.test(path) },
      { href: "/employees", label: "Tổ chức", active: /^\/(employees|departments|positions)(\/[^/]+)?$/.test(path) },
    ] : []),
    ...(user?.role === "ADMIN" ? [{ href: "/admin/users", label: "Quản trị hệ thống", active: path.startsWith("/admin") || path.startsWith("/settings") }] : []),
  ];
  const roles: Record<string, string> = { ADMIN: "Quản trị viên", HR: "Nhân sự", MANAGER: "Quản lý", EMPLOYEE: "Nhân viên" };
  return <header className="workspace-topbar">
    <Link href="/dashboard" className="brand">Insight<span>HR</span><small>Không gian làm việc</small></Link>
    <nav className="workspace-tabs" aria-label="Nhóm chức năng">{tabs.map((tab) => <Link key={tab.href} href={tab.href} aria-current={tab.active ? "location" : undefined}>{tab.label}</Link>)}</nav>
    {user && <Link href="/account" className="workspace-profile"><span className="profile-dot" aria-hidden="true">{user.role.slice(0, 1)}</span><span>{roles[user.role]}<small>Tài khoản của bạn</small></span></Link>}
  </header>;
}

export function WorkspaceNavigation() {
  const { user } = useAuth();
  const pathname = usePathname();
  const evaluation = /^\/employees\/[^/]+\/(kpis|feedback|performance)/.test(pathname ?? "");
  const isCurrent = (href: string) => evaluation ? href === "/review-cycles" : pathname === href || (href !== "/" && !!pathname?.startsWith(`${href}/`));
  const [expanded, setExpanded] = useState(false);
  const domain = user && ["HR", "MANAGER", "EMPLOYEE"].includes(user.role);
  const groups = [
    { label: "Không gian làm việc", items: [{ href: "/dashboard", label: "Tổng quan" }] },
    { label: "Cá nhân", items: [{ href: "/account", label: "Tài khoản" }, ...(user ? [{ href: "/feedback", label: "Phản hồi của tôi" }] : [])] },
    ...(domain ? [{ label: "Đánh giá", items: [{ href: "/review-cycles", label: "Chu kỳ đánh giá" }, { href: "/kpis", label: "Danh mục KPI" }, { href: "/ai-reports", label: "Tư vấn AI đã lưu" }, ...(user?.role === "HR" ? [{ href: "/feedback-administration", label: "Quản trị phản hồi" }] : [])] },
      { label: "Tổ chức", items: [{ href: "/employees", label: "Nhân viên" }, { href: "/departments", label: "Phòng ban" }, { href: "/positions", label: "Chức danh" }] }] : []),
    ...(user?.role === "ADMIN" ? [{ label: "Quản trị", items: [{ href: "/admin/users", label: "Quản lý tài khoản" }, { href: "/settings/scoring", label: "Cấu hình chấm điểm" }] }] : []),
    { label: "Hệ thống", items: [{ href: "/", label: "Trạng thái hệ thống" }] },
  ];
  const section = user?.role === "ADMIN" ? "Quản trị" :
    /^\/(employees|departments|positions)(\/[^/]+)?$/.test(pathname ?? "") ? "Tổ chức" :
    pathname === "/account" || pathname === "/feedback" || pathname?.startsWith("/feedback/") || pathname === "/" ? "Cá nhân" : "Đánh giá";
  const visible = groups.filter((group) => group.label === "Không gian làm việc" || group.label === "Cá nhân" || group.label === section || group.label === "Hệ thống" && pathname === "/account");
  return <><button className="navigation-toggle secondary" type="button" aria-controls="workspace-navigation" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)}>{expanded ? "Đóng menu" : "Mở menu"}</button><nav id="workspace-navigation" data-expanded={expanded} aria-label="Điều hướng không gian làm việc">{visible.map((group) => <div className="navigation-group" key={group.label}><span className="navigation-label">{group.label}</span>{group.items.map(({ href, label }) => <Link key={href} href={href} onClick={() => setExpanded(false)} aria-current={isCurrent(href) ? "page" : undefined}>{label}</Link>)}</div>)}</nav></>;
}
