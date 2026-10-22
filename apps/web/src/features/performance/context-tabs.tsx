import Link from "next/link";

export function EvaluationTabs({ employeeId, cycleId, active }: { employeeId: string; cycleId: string; active: "kpis" | "feedback" | "performance" }) {
  return <nav className="context-tabs" aria-label="Đánh giá trong cùng chu kỳ">{[
    ["kpis", "KPI & kết quả thực tế"], ["feedback", "Phản hồi 360"], ["performance", "Kết quả hiệu suất"],
  ].map(([path, label]) => <Link key={path} href={`/employees/${employeeId}/${path}?cycle_id=${encodeURIComponent(cycleId)}`} aria-current={active === path ? "page" : undefined}>{label}</Link>)}</nav>;
}
