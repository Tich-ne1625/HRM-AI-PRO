import Link from "next/link";
import type { ReactNode } from "react";
import { ProtectedRoute } from "../../features/auth/protected-route";
import { WorkspaceNavigation } from "../../features/organization/navigation";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default function ProtectedLayout({ children }: { children: ReactNode }) {
  return <div className="workspace"><a className="skip-link" href="#workspace-content">Đến nội dung chính</a><header className="workspace-header"><Link href="/account" className="brand">InsightHR<span className="brand-caption">Không gian quản trị nhân sự</span></Link>
    <WorkspaceNavigation />
  </header><main id="workspace-content" className="workspace-main" tabIndex={-1}><ProtectedRoute>{children}</ProtectedRoute></main></div>;
}
