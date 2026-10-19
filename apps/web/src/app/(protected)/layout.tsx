import Link from "next/link";
import type { ReactNode } from "react";
import { ProtectedRoute } from "../../features/auth/protected-route";
import { WorkspaceNavigation } from "../../features/organization/navigation";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default function ProtectedLayout({ children }: { children: ReactNode }) {
  return <div className="workspace"><header className="workspace-header"><Link href="/account" className="brand">InsightHR</Link>
    <WorkspaceNavigation />
  </header><main className="workspace-main"><ProtectedRoute>{children}</ProtectedRoute></main></div>;
}
