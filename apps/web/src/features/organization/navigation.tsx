"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAuth } from "../auth/auth-provider";

export function WorkspaceNavigation() {
  const { user } = useAuth();
  const pathname = usePathname();
  const [expanded, setExpanded] = useState(false);
  const domain = user && ["HR", "MANAGER", "EMPLOYEE"].includes(user.role);
  const groups = [
    { label: "Cá nhân", items: [{ href: "/account", label: "Tài khoản" }, ...(user ? [{ href: "/feedback", label: "Phản hồi của tôi" }] : [])] },
    ...(domain ? [{ label: "Đánh giá", items: [{ href: "/review-cycles", label: "Chu kỳ đánh giá" }, { href: "/kpis", label: "Danh mục KPI" }, ...(user?.role === "HR" ? [{ href: "/feedback-administration", label: "Quản trị phản hồi" }] : [])] },
      { label: "Tổ chức", items: [{ href: "/employees", label: "Nhân viên" }, { href: "/departments", label: "Phòng ban" }, { href: "/positions", label: "Chức danh" }] }] : []),
    ...(user?.role === "ADMIN" ? [{ label: "Quản trị", items: [{ href: "/admin/users", label: "Quản lý tài khoản" }, { href: "/settings/scoring", label: "Cấu hình chấm điểm" }] }] : []),
    { label: "Hệ thống", items: [{ href: "/", label: "Trạng thái hệ thống" }] },
  ];
  return <><button className="navigation-toggle secondary" type="button" aria-controls="workspace-navigation" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)}>{expanded ? "Đóng menu" : "Mở menu"}</button><nav id="workspace-navigation" data-expanded={expanded} aria-label="Điều hướng không gian làm việc">{groups.map((group) => <div className="navigation-group" key={group.label}><span className="navigation-label">{group.label}</span>{group.items.map(({ href, label }) => <Link key={href} href={href} onClick={() => setExpanded(false)} aria-current={pathname === href || (href !== "/" && pathname?.startsWith(`${href}/`)) ? "page" : undefined}>{label}</Link>)}</div>)}</nav></>;
}
