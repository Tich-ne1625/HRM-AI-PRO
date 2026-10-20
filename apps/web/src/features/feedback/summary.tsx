"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useAuth } from "../auth/auth-provider";
import { feedbackApi } from "./api";
import { FeedbackError, relationships, SubmissionContent } from "./shared";

export function FeedbackSummary({ employeeId, cycleId }: { employeeId: string; cycleId: string }) {
  const { user } = useAuth();
  if (!user || !["HR", "MANAGER", "EMPLOYEE"].includes(user.role)) return <p role="alert">Bạn không có quyền xem tổng hợp phản hồi.</p>;
  return <Summary employeeId={employeeId} cycleId={cycleId} />;
}
function Summary({ employeeId, cycleId }: { employeeId: string; cycleId: string }) {
  const { user } = useAuth();
  const query = useQuery({ queryKey: ["feedback", "summary", employeeId, cycleId, user?.id], queryFn: () => feedbackApi.summary(employeeId, cycleId) });
  if (query.isPending) return <p role="status">Đang tải tổng hợp phản hồi…</p>;
  if (query.isError) return <FeedbackError error={query.error} reload={() => { void query.refetch(); }} />;
  const row = query.data;
  return <><section className="auth-card wide"><div className="section-heading"><div><p className="eyebrow">PHẢN HỒI 360</p><h1>Tổng hợp phản hồi</h1></div><Link href={`/review-cycles/${cycleId}`}>Về chu kỳ</Link></div>
    <div className="row-actions"><Link href={`/employees/${employeeId}`}>Hồ sơ nhân viên</Link><Link href={`/employees/${employeeId}/kpis?cycle_id=${cycleId}`}>KPI cùng chu kỳ</Link>{user?.role === "HR" && <Link href={`/feedback-administration?participant_id=${row.participant_id}&cycle_id=${cycleId}`}>Quản trị phân công</Link>}</div>
    <div className="metric-grid"><div className="metric"><span>Phản hồi đã gửi</span><strong>{row.count}</strong></div><div className="metric"><span>Mức trung bình /5</span><strong>{row.mean ?? "—"}</strong></div><div className="metric"><span>Phản hồi bắt buộc</span><strong>{row.ready ? "Đã đủ" : "Chưa đủ"}</strong></div></div>
    <p>Đây là mức phản hồi trung bình, chưa phải điểm hiệu suất. Nhóm đồng nghiệp và cấp dưới chỉ hiện thống kê khi có ít nhất ba người gửi trong từng nhóm.</p>
    <p className="help-text">HR có quyền xem dữ liệu gốc. Thống kê tổng thể có thể cho phép suy luận trong nhóm nhỏ; hệ thống không cam kết ẩn danh tuyệt đối.</p>
  </section><section className="auth-card wide"><h2>Theo quan hệ đánh giá</h2><div className="feedback-cards">{row.groups.map((group) => <article className="inbox-card" key={group.relationship}><h3>{relationships[group.relationship]}</h3>{group.suppressed ? <p>Chưa đủ ba người gửi để hiển thị thống kê nhóm này.</p> : <><p><strong>{group.mean ?? "—"}/5</strong></p><p>{group.count} phản hồi đã gửi</p></>}</article>)}</div></section>
    {row.own_submission && <section className="auth-card wide"><h2>Phản hồi do bạn gửi</h2><SubmissionContent {...row.own_submission} /></section>}
  </>;
}
