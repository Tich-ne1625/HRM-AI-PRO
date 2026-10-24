"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { AISection } from "../ai/section";
import { useAuth } from "../auth/auth-provider";
import { ReviewAccess, ReviewError } from "../cycles/shared";
import { relationships, SubmissionContent } from "../feedback/shared";
import { Pagination } from "../organization/shared";
import { performanceApi, type Calculation, type FinalizationContext, type Report } from "./api";
import { EvaluationTabs } from "./context-tabs";

const states = { NOT_CALCULATED: "Chưa tính điểm", CURRENT: "Kết quả hiện tại", STALE: "Cần tính lại", FINALIZED: "Đã chốt kết quả" };
const issueLabels: Record<string, string> = {
  kpi_allocation_required: "Chưa phân bổ KPI cho nhân viên.",
  kpi_actual_required: "Có KPI chưa nhập kết quả thực tế.",
  required_feedback_incomplete: "Chưa đủ phản hồi bắt buộc. Kiểm tra tự đánh giá, quản lý và các phân công bắt buộc khác.",
  allocation_or_policy_invalid: "Phân bổ KPI hoặc cấu hình chưa phù hợp để tính điểm.",
  scoring_policy_incompatible: "Cấu hình của kỳ đánh giá chưa phù hợp để tính điểm.",
  evidence_inconsistent: "Dữ liệu chưa nhất quán. Liên hệ HR để kiểm tra.",
  cycle_not_active: "Chu kỳ chưa được kích hoạt.",
};

export function PerformanceReport(props: { employeeId: string; cycleId: string }) {
  return <ReviewAccess><ReportContent {...props} /></ReviewAccess>;
}

function ReportContent({ employeeId, cycleId }: { employeeId: string; cycleId: string }) {
  const { user } = useAuth();
  const cache = useQueryClient();
  const query = useQuery({ queryKey: ["performance", "report", employeeId, cycleId, user?.id], queryFn: () => performanceApi.report(employeeId, cycleId) });
  const [confirm, setConfirm] = useState(false);
  const refresh = async () => { setConfirm(false); await Promise.all(["performance", "reviews", "feedback", "ai"].map((key) => cache.invalidateQueries({ queryKey: [key] }))); };
  const calculate = useMutation({ mutationFn: () => performanceApi.calculate(employeeId, cycleId, query.data!.evidence_version), onSuccess: refresh });
  if (query.isPending) return <p role="status">Đang tải báo cáo hiệu suất…</p>;
  if (query.isError) return <ReviewError error={query.error} reload={() => { void refresh(); }} />;
  const row = query.data;
  return <>
    <section className="auth-card wide">
      <div className="section-heading"><div><p className="eyebrow">BÁO CÁO HIỆU SUẤT</p><h1>{row.display_name}</h1><p>{row.employee_code} · {row.cycle_name}</p></div><Link href={`/review-cycles/${cycleId}`}>← Về chu kỳ</Link></div>
      <EvaluationTabs employeeId={employeeId} cycleId={cycleId} active="performance" />
      <div className="section-heading"><span className={`badge ${row.state === "FINALIZED" ? "active" : ""}`}>{states[row.state]}</span><button type="button" className="secondary" disabled={query.isFetching || calculate.isPending} onClick={() => { calculate.reset(); void refresh(); }}>Làm mới dữ liệu</button></div>
      {row.state === "STALE" && <p className="state-notice" role="status">KPI hoặc phản hồi đã thay đổi. Điểm cũ nằm trong lịch sử; cần tính lại trước khi chốt.</p>}
      {row.state === "NOT_CALCULATED" && <p>Hoàn tất KPI và phản hồi bắt buộc, sau đó HR hoặc quản lý trực tiếp tính điểm.</p>}
      {!row.readiness.ready && <div className="state-notice"><h2>Việc cần hoàn thành</h2><ul>{[...new Set(row.readiness.issues.map((issue) => issue.code))].map((code) => <li key={code}>{issueLabels[code] ?? "Kiểm tra lại dữ liệu đánh giá."}</li>)}</ul><div className="row-actions"><Link href={`/employees/${employeeId}/kpis?cycle_id=${cycleId}`}>Kiểm tra KPI</Link>{user?.role === "HR" && <Link href={`/feedback-administration?participant_id=${row.participant_id}&cycle_id=${cycleId}`}>Kiểm tra phân công phản hồi</Link>}</div></div>}
      {row.current_result && <ScoreMetrics row={row.current_result} />}
      {row.finalized_at && <p role="status">Đã chốt lúc {new Date(row.finalized_at).toLocaleString("vi-VN")}.</p>}
      <div className="row-actions">
        {row.can_calculate && <button disabled={calculate.isPending || confirm || calculate.isError} onClick={() => calculate.mutate()}>{calculate.isPending ? "Đang tính…" : row.state === "NOT_CALCULATED" ? "Tính điểm hiệu suất" : "Tính lại điểm"}</button>}
        {row.can_finalize && <button className="secondary" disabled={calculate.isPending} onClick={() => setConfirm(true)}>Chốt kết quả</button>}
      </div>
      {calculate.isError && <ReviewError error={calculate.error} reload={() => { calculate.reset(); void refresh(); }} />}
      {confirm && row.can_finalize && row.review_id && <FinalizeReview key={`${row.review_id}-${row.evidence_version}-${row.current_result?.calculation_version}`} report={row} onDone={refresh} onCancel={() => setConfirm(false)} />}
    </section>
    <AISection report={row} />
    {row.current_result && <CalculationDetail row={row.current_result} />}
    {row.review_id && <History reviewId={row.review_id} />}
  </>;
}

function ScoreMetrics({ row }: { row: Calculation }) {
  return <div className="metric-grid"><div className="metric primary"><span>Điểm hiệu suất</span><strong>{row.final_score}</strong></div><div className="metric"><span>Điểm KPI · {row.policy.kpi_weight}%</span><strong>{row.kpi_score}</strong></div><div className="metric"><span>Điểm phản hồi · {row.policy.feedback_weight}%</span><strong>{row.feedback_score}</strong></div></div>;
}

function CalculationDetail({ row }: { row: Calculation }) {
  return <details className="auth-card wide calculation-disclosure"><summary>Chi tiết lần tính {row.calculation_version}</summary>
    <p className="help-text">Tính lúc {new Date(row.calculated_at).toLocaleString("vi-VN")} · Điểm KPI giới hạn ở {row.policy.kpi_cap ?? "không giới hạn"}. Điểm thành phần và tổng được làm tròn riêng đến hai chữ số thập phân.</p>
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Kết quả và lịch sử tính điểm, có thể cuộn ngang"><table className="score-table"><caption>Kết quả KPI theo dữ liệu của lần tính này</caption><thead><tr><th>KPI</th><th>Mục tiêu</th><th>Thực tế</th><th>Trọng số</th><th>Điểm gốc</th><th>Sau giới hạn</th><th>Đóng góp</th></tr></thead><tbody>{row.items.map((item) => <tr key={item.id}><td><strong>{item.name}</strong><br /><small>{item.code} · {item.unit} · {item.direction === "LOWER_IS_BETTER" ? "Càng thấp càng tốt" : "Càng cao càng tốt"}</small></td><td>{item.target}</td><td>{item.actual}</td><td>{item.weight}%</td><td>{item.raw_score}</td><td>{item.normalized_score}</td><td>{item.weighted_score}</td></tr>)}</tbody></table></div>
    <h3>Phản hồi được tính vào kết quả</h3><p>{row.feedback.count} phản hồi · Trung bình {row.feedback.mean ?? "—"}/5. Mỗi phản hồi đã gửi có trọng số bằng nhau.</p>
    <div className="feedback-cards">{row.feedback.groups.map((group) => <article className="inbox-card" key={group.relationship}><h3>{relationships[group.relationship]}</h3><p>{group.suppressed ? "Chưa đủ ba người gửi để hiển thị thống kê nhóm." : `${group.mean ?? "—"}/5 · ${group.count} phản hồi`}</p></article>)}</div>
    {row.feedback.own_submission && <><h3>Phản hồi do bạn gửi trong lần tính này</h3><SubmissionContent {...row.feedback.own_submission} /></>}
  </details>;
}

function FinalizeReview({ report, onDone, onCancel }: { report: Report; onDone: () => Promise<void>; onCancel: () => void }) {
  const { user } = useAuth();
  const context = useQuery({ queryKey: ["performance", "finalization", report.review_id, report.evidence_version, user?.id], queryFn: () => performanceApi.context(report.review_id!), staleTime: 0 });
  const mutation = useMutation({ mutationFn: (value: FinalizationContext) => performanceApi.finalize(report.review_id!, value), onSuccess: onDone });
  return <section className="confirmation" role="group" aria-label="Xác nhận chốt kết quả"><h2>Chốt kết quả đánh giá</h2><p>Sau khi chốt, KPI và phản hồi của nhân viên trong kỳ này sẽ khóa chỉnh sửa.</p>
    {context.isPending && <p role="status">Đang kiểm tra điều kiện chốt…</p>}
    {context.isError && <ReviewError error={context.error} reload={onCancel} />}
    {context.data && <FinalizationDecision key={`${context.data.evidence_version}-${context.data.calculation_version}-${context.data.open_optional_count}`} context={context.data} pending={mutation.isPending} blocked={mutation.isError || context.isFetching} onConfirm={() => mutation.mutate(context.data!)} onCancel={onCancel} />}
    {mutation.isError && <ReviewError error={mutation.error} reload={onCancel} />}
  </section>;
}

function FinalizationDecision({ context, pending, blocked, onConfirm, onCancel }: { context: FinalizationContext; pending: boolean; blocked: boolean; onConfirm: () => void; onCancel: () => void }) {
  const [ack, setAck] = useState(false);
  return <><p>Còn <strong>{context.open_optional_count}</strong> phân công không bắt buộc chưa gửi. Chốt kết quả sẽ khóa việc gửi các phản hồi này.</p>
    <label className="checkbox-label"><input type="checkbox" checked={ack} disabled={pending} onChange={(event) => setAck(event.target.checked)} />Tôi đã kiểm tra kết quả và đồng ý chốt với số phân công chưa gửi ở trên.</label>
    <div className="row-actions"><button disabled={!ack || !context.readiness.ready || pending || blocked} onClick={onConfirm}>Xác nhận chốt kết quả</button><button className="secondary" disabled={pending} onClick={onCancel}>Hủy</button></div>
  </>;
}

function History({ reviewId }: { reviewId: string }) {
  const { user } = useAuth();
  const [page, setPage] = useState(1), [selected, setSelected] = useState<number | null>(null);
  const history = useQuery({ queryKey: ["performance", "revisions", reviewId, page, user?.id], queryFn: () => performanceApi.revisions(reviewId, page) });
  const detail = useQuery({ queryKey: ["performance", "revision", reviewId, selected, user?.id], queryFn: () => performanceApi.revision(reviewId, selected!), enabled: selected !== null });
  return <section className="auth-card wide"><h2>Lịch sử tính điểm</h2><p>Các lần tính trước được lưu để đối chiếu. Điểm lịch sử có thể khác kết quả hiện tại.</p>
    {history.isPending && <p role="status">Đang tải lịch sử…</p>}{history.isError && <ReviewError error={history.error} reload={() => { void history.refetch(); }} />}
    {!history.isError && history.data && <><div className="table-scroll" tabIndex={0} role="region" aria-label="Kết quả và lịch sử tính điểm, có thể cuộn ngang"><table><caption>Các lần tính, mới nhất trước</caption><thead><tr><th>Lần tính</th><th>Thời gian</th><th>Điểm hiệu suất</th><th>Thao tác</th></tr></thead><tbody>{history.data.items.map((row) => <tr key={row.calculation_version}><td>{row.calculation_version}</td><td>{new Date(row.calculated_at).toLocaleString("vi-VN")}</td><td>{row.final_score}</td><td><button className="secondary" onClick={() => setSelected(row.calculation_version)}>Xem lần {row.calculation_version}</button></td></tr>)}</tbody></table></div><Pagination page={page} total={history.data.total} pending={history.isFetching} onPage={setPage} /></>}
    {selected !== null && <div className="state-notice"><div className="section-heading"><h3>Đang xem lịch sử · Lần {selected}</h3><button className="secondary" onClick={() => setSelected(null)}>Đóng chi tiết lịch sử</button></div>{detail.isPending && <p role="status">Đang tải lần tính…</p>}{detail.isError && <ReviewError error={detail.error} />}{!detail.isError && detail.data && <><ScoreMetrics row={detail.data} /><CalculationDetail row={detail.data} /></>}</div>}
  </section>;
}
