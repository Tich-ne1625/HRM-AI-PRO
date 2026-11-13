"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useAuth } from "../auth/auth-provider";
import { workspaceRouteAllowed } from "./navigation-model";

export function WorkspaceRouteAccess({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const path = usePathname() ?? "";
  if (!user || !workspaceRouteAllowed(user.role, path)) return <section className="auth-card"><h1>Trang không thuộc vai trò của bạn</h1><p>Chọn một chức năng trong menu để tiếp tục.</p><Link href="/dashboard">Về tổng quan</Link></section>;
  return children;
}
