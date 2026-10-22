import { PerformanceReport } from "../../../../../features/performance/report";

export default async function EmployeePerformancePage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ cycle_id?: string }> }) {
  const [{ id }, { cycle_id }] = await Promise.all([params, searchParams]);
  if (!cycle_id) return <p role="alert">Hãy chọn chu kỳ từ danh sách người tham gia để xem kết quả.</p>;
  return <PerformanceReport employeeId={id} cycleId={cycle_id} />;
}
