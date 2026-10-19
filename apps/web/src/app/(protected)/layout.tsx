import Link from "next/link";
import type { ReactNode } from "react";
import { ProtectedRoute } from "../../features/auth/protected-route";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default function ProtectedLayout({ children }: { children: ReactNode }) {
  return <div className="workspace"><header className="workspace-header"><Link href="/account" className="brand">InsightHR</Link>
    <nav aria-label="Điều hướng tài khoản"><Link href="/account">Tài khoản</Link><Link href="/">Trạng thái hệ thống</Link></nav>
  </header><main className="workspace-main"><ProtectedRoute>{children}</ProtectedRoute></main></div>;
}
