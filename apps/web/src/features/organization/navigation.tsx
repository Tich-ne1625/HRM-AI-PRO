"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAuth } from "../auth/auth-provider";
import { navigationGroups, navigationPath } from "../workspace/navigation-model";

export function WorkspaceHeader() {
  const { user } = useAuth();
  const path = navigationPath(usePathname() ?? "");
  const groups = user ? navigationGroups(user.role) : [];
  const roles = { ADMIN: "Quản trị viên", HR: "Nhân sự", MANAGER: "Quản lý", EMPLOYEE: "Nhân viên" };
  return <header className="workspace-topbar">
    <Link href="/dashboard" className="brand">Insight<span>HR</span><small>Không gian làm việc</small></Link>
    <nav className="workspace-tabs" aria-label="Nhóm chức năng">{groups.map((group) => <Link key={group.href} href={group.href}
      aria-current={group.items.some((item) => path === item.href || path.startsWith(`${item.href}/`)) ? "location" : undefined}>{group.label}</Link>)}</nav>
    {user && <Link href="/account" className="workspace-profile"><span className="profile-dot" aria-hidden="true">{user.role.slice(0, 1)}</span><span>{roles[user.role]}<small>Tài khoản của bạn</small></span></Link>}
  </header>;
}

export function WorkspaceNavigation() {
  const { user } = useAuth();
  const pathname = navigationPath(usePathname() ?? "");
  const [expanded, setExpanded] = useState(false);
  const groups = user ? navigationGroups(user.role) : [];
  return <><button className="navigation-toggle secondary" type="button" aria-controls="workspace-navigation" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>{expanded ? "Đóng menu" : "Mở menu"}</button>
    <nav id="workspace-navigation" data-expanded={expanded} aria-label="Điều hướng không gian làm việc">{groups.map((group) => <div className="navigation-group" key={group.href}>
      <span className="navigation-label">{group.label}</span>{group.items.map(({ href, label }) => <Link key={href} href={href} onClick={() => setExpanded(false)}
        aria-current={pathname === href || pathname.startsWith(`${href}/`) ? "page" : undefined}>{label}</Link>)}
    </div>)}</nav></>;
}
