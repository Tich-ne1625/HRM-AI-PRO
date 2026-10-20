import { FeedbackSummary } from "../../../../../features/feedback/summary";

export default async function EmployeeFeedbackPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ cycle_id?: string }> }) {
  const [{ id }, { cycle_id }] = await Promise.all([params, searchParams]);
  if (!cycle_id) return <p role="alert">Hãy chọn chu kỳ từ danh sách người tham gia để xem phản hồi.</p>;
  return <FeedbackSummary employeeId={id} cycleId={cycle_id} />;
}
