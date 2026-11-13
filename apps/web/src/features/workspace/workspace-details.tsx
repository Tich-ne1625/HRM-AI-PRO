"use client";

import dynamic from "next/dynamic";
import { usePathname } from "next/navigation";
import { useMemo, useState, type ReactNode } from "react";
import { useAuth } from "../auth/auth-provider";
import type { UserRole } from "../auth/types";
import { DetailContext, type DetailLocation } from "./detail-context";
import { WorkspaceDialog } from "./dialog";
import { workspaceRouteAllowed } from "./navigation-model";

const loading = () => <p role="status">Đang mở chi tiết…</p>;
const CycleDetail = dynamic(() => import("../cycles/cycle-detail").then((module) => module.CycleDetail), { loading });
const EmployeeDetail = dynamic(() => import("../organization/employee-detail").then((module) => module.EmployeeDetail), { loading });
const EmployeeKpis = dynamic(() => import("../kpis/employee-kpis").then((module) => module.EmployeeKpis), { loading });
const PerformanceReport = dynamic(() => import("../performance/report").then((module) => module.PerformanceReport), { loading });
const FeedbackSummary = dynamic(() => import("../feedback/summary").then((module) => module.FeedbackSummary), { loading });
const FeedbackDetail = dynamic(() => import("../feedback/detail").then((module) => module.FeedbackDetail), { loading });
const FeedbackAdministration = dynamic(() => import("../feedback/administration").then((module) => module.FeedbackAdministration), { loading });

export function WorkspaceDetails({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const path = usePathname();
  return <DetailWorkspace key={`${user?.id}:${user?.role}:${path}`} role={user?.role}>{children}</DetailWorkspace>;
}

function DetailWorkspace({ children, role }: { children: ReactNode; role: UserRole | undefined }) {
  const [location, setLocation] = useState<DetailLocation | null>(null);
  const context = useMemo(() => ({ open: setLocation, close: () => setLocation(null), active: !!location }), [location]);
  const titles = { cycle: "Chu kỳ đánh giá", employee: "Hồ sơ nhân viên", kpis: "Hồ sơ đánh giá", "feedback-summary": "Hồ sơ đánh giá", performance: "Hồ sơ đánh giá", assignment: "Phiếu phản hồi", administration: "Phân công phản hồi" };
  const allowed = location && role && workspaceRouteAllowed(role, new URL(location.href, "http://workspace.local").pathname);
  return <DetailContext value={context}>{children}
    {location && <WorkspaceDialog title={titles[location.kind]} close={context.close} focusKey={location.href}>
      {!allowed ? <p role="alert">Chức năng không thuộc vai trò của bạn.</p> : <div key={`${location.kind}:${location.id}:${location.cycle}`}>
        {location.kind === "cycle" && <CycleDetail id={location.id} />}
        {location.kind === "employee" && <EmployeeDetail id={location.id} />}
        {location.kind === "kpis" && <EmployeeKpis id={location.id} cycle={location.cycle} />}
        {location.kind === "performance" && <PerformanceReport employeeId={location.id} cycleId={location.cycle} />}
        {location.kind === "feedback-summary" && <FeedbackSummary employeeId={location.id} cycleId={location.cycle} />}
        {location.kind === "assignment" && <FeedbackDetail id={location.id} />}
        {location.kind === "administration" && <FeedbackAdministration participantId={location.id} cycleId={location.cycle} />}
      </div>}
    </WorkspaceDialog>}
  </DetailContext>;
}
