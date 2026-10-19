"use client";

import Link from "next/link";
import { useAuth } from "../auth/auth-provider";

export function WorkspaceNavigation() {
  const { user } = useAuth();
  const domain = user && ["HR", "MANAGER", "EMPLOYEE"].includes(user.role);
  return <nav aria-label="Điều hướng không gian làm việc">
    <Link href="/account">Tài khoản</Link>
    {user?.role === "ADMIN" && <Link href="/admin/users">Quản lý tài khoản</Link>}
    {domain && <><Link href="/employees">Nhân viên</Link><Link href="/departments">Phòng ban</Link><Link href="/positions">Chức danh</Link></>}
    <Link href="/">Trạng thái hệ thống</Link>
  </nav>;
}
