"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "../workspace/detail-link";
import { useContext, useEffect, useId, useRef, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { ApiClientError } from "../../lib/api-client";
import { useAuth } from "../auth/auth-provider";
import { DetailContext } from "../workspace/detail-context";
import { Pagination } from "../organization/shared";
import { feedbackApi, type Administration, type AdministrationContext, type BatchAssignmentInput, type ReviewerOption, type Reason, type Relationship } from "./api";
import { AssignmentWorkspace } from "./assignment-workspace";
import { ReviewerMultiPicker } from "./reviewer-multi-picker";
import { deadline, FeedbackError, relationships, statuses, SubmissionContent, useDisplayClock, useFeedbackRefresh, versions } from "./shared";

const deadlineSchema = z.string().refine((v) => !v || Number.isFinite(Date.parse(v)), "Thời hạn không hợp lệ.");
const createSchema = z.object({ relationship: z.enum(["SELF", "MANAGER", "PEER", "SUBORDINATE"]),
  reviewer_id: z.string(), required: z.boolean(), due_at: deadlineSchema }).superRefine((value, context) => {
    if ((value.relationship === "SELF" || value.relationship === "MANAGER") && !value.reviewer_id) context.addIssue({ code: "custom", path: ["reviewer_id"], message: "Chọn người đánh giá." });
  });
const toUtc = (value: string) => value ? new Date(value).toISOString() : null;
const localDate = (value: string | null) => value ? new Date(Date.parse(value) - new Date(value).getTimezoneOffset() * 60_000).toISOString().slice(0, 16) : "";

export function FeedbackAdministration({ participantId, cycleId }: { participantId?: string; cycleId?: string }) {
  const { user } = useAuth();
  if (user?.role !== "HR") return <p role="alert">Chỉ HR được quản trị phân công và đọc phản hồi gốc.</p>;
  return <AdministrationWorkspaceRoot key={`${participantId ?? "all"}:${cycleId ?? "all"}`} participantId={participantId} cycleId={cycleId} />;
}
function AdministrationWorkspaceRoot({ participantId, cycleId }: { participantId?: string; cycleId?: string }) {
  const details = useContext(DetailContext);
  const [selected, setSelected] = useState(participantId), [cycle, setCycle] = useState(cycleId);
  return <><section className="auth-card wide"><p className="eyebrow">NHIỆM VỤ HR · TỔ CHỨC THU THẬP PHẢN HỒI</p><h1>Phân công phản hồi</h1><p>HR chọn ai cần được đánh giá, giao phiếu cho đúng người và theo dõi việc gửi. Quản lý nhập KPI và tính điểm; HR kiểm tra, chốt kết quả.</p>{!participantId && <ol className="assignment-steps"><li>Chọn kỳ và người được đánh giá</li><li>Chọn quan hệ và người gửi phản hồi</li><li>Kiểm tra, giao phiếu và theo dõi</li></ol>}</section>
    {!participantId && <AssignmentWorkspace initialCycle={cycleId} selected={selected} onSelect={(row, nextCycle) => {
      if (row && details) { details.open({ kind: "administration", id: row.id, cycle: nextCycle, href: `/feedback-administration?participant_id=${row.id}&cycle_id=${nextCycle}` }); return; }
      setSelected(row?.id); setCycle(nextCycle || undefined);
    }} />}
    <AdministrationPage key={`${selected ?? "all"}:${cycle ?? "all"}`} participantId={selected} cycleId={cycle} />
  </>;
}
function AdministrationPage({ participantId, cycleId }: { participantId?: string; cycleId?: string }) {
  const { user } = useAuth();
  const now = useDisplayClock();
  const [page, setPage] = useState(1), [selected, setSelected] = useState<Administration | null>(null);
  const [generation, setGeneration] = useState(0);
  const [savedCount, setSavedCount] = useState(0);
  const context = useQuery({ queryKey: ["feedback", "administration", "context", participantId, user?.id],
    queryFn: () => feedbackApi.context(participantId!), enabled: !!participantId });
  const rows = useQuery({ queryKey: ["feedback", "administration", "list", participantId, cycleId, page, user?.id],
    queryFn: () => feedbackApi.administration({ participant_id: participantId, cycle_id: cycleId, page }) });
  const refresh = useFeedbackRefresh();
  const saved = async (count?: number) => { await refresh(); setGeneration((v) => v + 1); if (count) setSavedCount(count); };
  return <><section className="auth-card wide"><div className="section-heading"><div><p className="eyebrow">{participantId ? "BƯỚC 2 · CHỌN NGƯỜI ĐÁNH GIÁ" : "THEO DÕI PHÂN CÔNG"}</p><h2>{participantId ? "Hồ sơ đang phân công" : "Các phiếu đã giao"}</h2></div><Link href="/feedback">Phản hồi của tôi</Link></div>
    <p>Giao đúng người, theo dõi phản hồi bắt buộc và xử lý phân công bị chặn. Nội dung gốc chỉ hiển thị cho HR có quyền.</p>
    {context.data ? <><h2>{context.data.employee_code} · {context.data.display_name}</h2><div className="row-actions"><Link href={`/review-cycles/${context.data.cycle_id}`}>Về người tham gia chu kỳ</Link><Link href={`/employees/${context.data.employee_id}/feedback?cycle_id=${context.data.cycle_id}`}>Xem bản tổng hợp</Link><Link href={`/employees/${context.data.employee_id}/kpis?cycle_id=${context.data.cycle_id}`}>KPI cùng chu kỳ</Link></div>
      <details className="assignment-coverage"><summary>Tiến độ phản hồi bắt buộc: {context.data.coverage.ready ? "Đã đủ" : "Chưa đủ"}</summary><div className="metric-grid"><div className="metric"><span>Phản hồi bắt buộc</span><strong>{context.data.coverage.ready ? "Đã đủ" : "Chưa đủ"}</strong></div><div className="metric"><span>Chưa gửi bắt buộc</span><strong>{context.data.coverage.pending_required}</strong></div><div className="metric"><span>Tài khoản bị khóa</span><strong>{context.data.coverage.blocked_required}</strong></div></div>
      {!!context.data.coverage.missing_relationships.length && <p>Cần phản hồi đã gửi từ: {context.data.coverage.missing_relationships.map((r) => relationships[r]).join(", ")}.</p>}
      <p className="help-text">Tự đánh giá và quản lý dùng đúng tài khoản tại lúc kích hoạt. Nếu tài khoản bị khóa, ADMIN cần khôi phục; không tự giao cho quản lý mới.</p></details></> : !participantId && <p>Chọn nhân viên ở bước 1 để giao phiếu mới. Danh sách dưới đây giúp theo dõi các phân công hiện có.</p>}
    {context.isError && <FeedbackError error={context.error} reload={() => { void context.refetch(); }} />}
  </section>
    {!!savedCount && <p className="assignment-success" role="status">Đã giao {savedCount} phiếu. Mỗi người được chọn nhận một phiếu trong Phản hồi của tôi và thông báo riêng.</p>}
    {context.data && context.data.cycle_status === "ACTIVE" && !context.data.finalized && <section className="auth-card wide"><h2>Giao phiếu phản hồi</h2><CreateForm key={`${participantId}-${generation}`} context={context.data} saved={saved} /></section>}
    {context.data && (context.data.cycle_status !== "ACTIVE" || context.data.finalized) && <p className="state-notice">Hồ sơ đã chốt hoặc kỳ đã đóng. Chỉ xem phân công; không thể giao thêm.</p>}
    <section className="auth-card wide"><div className="section-heading"><h2>Phân công và phản hồi gốc</h2>{!rows.isError && rows.data && <span className="badge">{rows.data.total} phân công</span>}</div>
      {rows.isPending && <p role="status">Đang tải phân công…</p>}{rows.isError && <FeedbackError error={rows.error} reload={() => { void rows.refetch(); }} />}
      {!rows.isError && rows.data && <><div className="table-scroll" tabIndex={0} aria-label="Bảng phân công phản hồi"><table><caption>Danh sách trong phạm vi quản trị HR</caption><thead><tr><th>Nhân viên / Chu kỳ</th><th>Người đánh giá</th><th>Quan hệ</th><th>Trạng thái / Hạn</th><th>Thao tác</th></tr></thead><tbody>{rows.data.items.map((row) => <tr key={row.id}><td><Link href={`/feedback-administration?participant_id=${row.participant_id}&cycle_id=${row.cycle_id}`}>{row.employee_code} · {row.display_name}</Link><br /><small>{row.cycle_name}</small></td><td>{row.reviewer_name}{!row.reviewer_active && <p className="field-warning">Tài khoản bị khóa</p>}</td><td>{relationships[row.relationship]}<br /><small>{row.required ? "Bắt buộc" : "Tùy chọn"}</small></td><td><span className="badge">{statuses[row.status]}</span>{row.status === "OPEN" && row.due_at && now >= Date.parse(row.due_at) && <p className="field-warning">Đã quá hạn — cần gia hạn để gửi</p>}<br /><small>{deadline(row.due_at)}</small></td><td><button className="secondary" onClick={() => setSelected(row)}>Mở phân công {row.reviewer_name}</button></td></tr>)}</tbody></table></div>
        {!rows.data.items.length && <p className="empty-state">Chưa có phân công. HR cần giao SELF và MANAGER trước khi đủ phản hồi bắt buộc.</p>}
        <Pagination page={page} total={rows.data.total} pending={rows.isFetching} onPage={setPage} /></>}
    </section>
    {selected && <AssignmentEditor key={selected.id} initial={selected} close={() => setSelected(null)} saved={saved} />}
  </>;
}

function ReviewerPicker({ participantId, relationship, value, onChange, allowCancelled = false }: {
  participantId: string; relationship: Relationship; value: string; onChange: (value: string) => void; allowCancelled?: boolean;
}) {
  const id = useId();
  const [page, setPage] = useState(1), [search, setSearch] = useState(""), [q, setQ] = useState("");
  useEffect(() => { if (search === q) return; const timer = setTimeout(() => { setQ(search); setPage(1); }, 300); return () => clearTimeout(timer); }, [search, q]);
  const { user } = useAuth();
  const query = useQuery({ queryKey: ["feedback", "administration", "options", participantId, relationship, page, q, user?.id],
    queryFn: () => feedbackApi.options(participantId, relationship, { page, q }) });
  return <div className="reviewer-picker"><label htmlFor={`${id}-search`}>Tìm người đánh giá theo mã hoặc tên</label><input id={`${id}-search`} maxLength={100} value={search} onChange={(e) => { setSearch(e.target.value); onChange(""); }} />
    <label htmlFor={`${id}-reviewer`}>Người đánh giá hợp lệ</label><select id={`${id}-reviewer`} value={value} onChange={(e) => onChange(e.target.value)}><option value="">Chọn người đánh giá</option>{query.data?.items.map((r) => <option key={r.reviewer_id} value={r.reviewer_id} disabled={!r.is_active || (!!r.existing_assignment_id && !(allowCancelled && r.existing_status === "CANCELLED"))}>{r.employee_code} · {r.display_name}{!r.is_active ? " — Tài khoản bị khóa" : r.existing_status === "CANCELLED" ? " — Đã hủy" : r.existing_assignment_id ? " — Đã phân công" : ""}</option>)}</select>
    {query.isPending && <p role="status">Đang tìm người đánh giá…</p>}{query.isError && <FeedbackError error={query.error} />}
    {!query.isError && query.data && <><Pagination page={page} total={query.data.total} pending={query.isFetching} onPage={(next) => { onChange(""); setPage(next); }} />{!query.data.items.length && <p>Không có người hợp lệ cho quan hệ này.</p>}{query.data.items.filter((r) => r.existing_status === "CANCELLED").map((r) => <p className="help-text" key={r.reviewer_id}><Link href={`/feedback-administration?participant_id=${participantId}`}>{r.display_name} đã có phân công bị hủy; mở phân công bên dưới để khôi phục.</Link></p>)}</>}
  </div>;
}
function CreateForm({ context, saved }: { context: AdministrationContext; saved: (count?: number) => Promise<void> }) {
  const [captured, setCaptured] = useState(context.evidence_version), [reloadError, setReloadError] = useState<Error | null>(null);
  const [selected, setSelected] = useState<ReviewerOption[]>([]), [selecting, setSelecting] = useState(false);
  const [preview, setPreview] = useState<{ body: BatchAssignmentInput; rows: ReviewerOption[] } | null>(null);
  const form = useForm<z.infer<typeof createSchema>>({ resolver: zodResolver(createSchema), defaultValues: { relationship: "SELF", reviewer_id: "", required: false, due_at: "" } });
  const [relation, reviewer, isRequired] = useWatch({ control: form.control, name: ["relationship", "reviewer_id", "required"] });
  const mandatory = relation === "SELF" || relation === "MANAGER";
  const mutation = useMutation({ mutationFn: (values: z.infer<typeof createSchema>) => feedbackApi.create({ ...values,
    participant_id: context.participant_id, expected_evidence_version: captured, due_at: toUtc(values.due_at), required: mandatory || values.required }), onSuccess: () => saved(1) });
  const batch = useMutation({ mutationFn: feedbackApi.createBatch, onSuccess: (result) => saved(result.created_count) });
  const blocked = batch.error instanceof ApiClientError ? selected.filter((row) => (batch.error as ApiClientError).details.some((detail) => detail.reviewer_id === row.reviewer_id)) : [];
  const reload = async () => { try { const latest = await feedbackApi.context(context.participant_id); setCaptured(latest.evidence_version); setPreview(null); mutation.reset(); batch.reset(); setReloadError(null); } catch (e) { setReloadError(e as Error); } };
  return <form onSubmit={form.handleSubmit((values) => {
    if (mandatory) mutation.mutate(values);
    else if (!selected.length) form.setError("reviewer_id", { message: "Chọn ít nhất một người đánh giá." });
    else setPreview({ body: { participant_id: context.participant_id, reviewer_ids: selected.map((row) => row.reviewer_id), relationship: values.relationship as "PEER" | "SUBORDINATE", required: values.required, due_at: toUtc(values.due_at), expected_evidence_version: captured }, rows: [...selected] });
  })}><fieldset disabled={mutation.isPending || batch.isPending || selecting || !!preview}><div><label htmlFor="feedback-relationship">Quan hệ người đánh giá</label><select id="feedback-relationship" {...form.register("relationship", { onChange: () => { form.setValue("reviewer_id", ""); form.clearErrors("reviewer_id"); setSelected([]); } })}>{Object.entries(relationships).map(([v, label]) => <option value={v} key={v}>{label}</option>)}</select>
    {mandatory ? <ReviewerPicker key={relation} participantId={context.participant_id} relationship={relation} value={reviewer} onChange={(v) => form.setValue("reviewer_id", v, { shouldValidate: true })} /> : <ReviewerMultiPicker key={relation} participant={context.participant_id} relationship={relation} limit={Math.max(0, 100 - (context.active_assignment_count ?? 0))} value={selected} onChange={(rows) => { setSelected(rows); form.clearErrors("reviewer_id"); }} onBusy={setSelecting} />}{form.formState.errors.reviewer_id && <p role="alert">{form.formState.errors.reviewer_id.message}</p>}</div>
    <div><label htmlFor="assignment-due">Hạn gửi (múi giờ thiết bị)</label><input id="assignment-due" type="datetime-local" {...form.register("due_at")} /><p className="help-text">Áp dụng cùng thời hạn cho những người trong lượt giao này. Để trống nếu không đặt hạn riêng.</p><label className="checkbox-label"><input type="checkbox" {...form.register("required")} checked={mandatory || isRequired} disabled={mandatory} />Bắt buộc hoàn thành</label><p className="help-text">Tự đánh giá và quản lý luôn bắt buộc, mỗi quan hệ dùng một người đúng tài khoản đã đóng băng.</p></div><button disabled={mutation.isPending || batch.isPending || selecting || (!mandatory && selected.length > 100 - (context.active_assignment_count ?? 0))}>{mandatory ? "Giao phản hồi" : `Xem lại ${selected.length} người đã chọn`}</button></fieldset>
    {preview && <section className="confirmation" aria-label="Xác nhận phân công hàng loạt"><h3>Giao {preview.rows.length} người phản hồi về {context.display_name}</h3><p>{relationships[preview.body.relationship]} · {preview.body.required ? "Bắt buộc" : "Tùy chọn"} · {deadline(preview.body.due_at)}</p><ul className="assignment-preview">{preview.rows.map((row) => <li key={row.reviewer_id}>{row.employee_code} · {row.display_name}</li>)}</ul><p>Mỗi người trong danh sách nhận một phiếu đánh giá nhân viên này và thông báo riêng. Nếu có người không còn hợp lệ, cả lượt giao sẽ không được lưu.</p><div className="row-actions"><button type="button" disabled={batch.isPending || batch.isError} onClick={() => batch.mutate(preview.body)}>Xác nhận giao {preview.rows.length} phiếu</button><button type="button" className="secondary" disabled={batch.isPending} onClick={() => setPreview(null)}>Quay lại chỉnh sửa</button></div></section>}
    {mutation.isError && <FeedbackError error={mutation.error} reload={() => { void reload(); }} />}{batch.isError && <><p>Cả lượt giao chưa được lưu. Tải lại phiên bản và kiểm tra danh sách trước khi xác nhận lại.</p><FeedbackError error={batch.error} reload={() => { void reload(); }} />{!!blocked.length && <p>Người cần kiểm tra: {blocked.map((row) => `${row.employee_code} · ${row.display_name}`).join(", ")}.</p>}</>}{reloadError && <FeedbackError error={reloadError} />}</form>;
}

function AssignmentEditor({ initial, close, saved }: { initial: Administration; close: () => void; saved: () => Promise<void> }) {
  const panel = useRef<HTMLElement>(null);
  useEffect(() => { panel.current?.focus(); panel.current?.scrollIntoView?.({ block: "start", behavior: "smooth" }); }, []);
  const [row, setRow] = useState(initial), [due, setDue] = useState(localDate(initial.due_at)), [required, setRequired] = useState(initial.required);
  const [action, setAction] = useState<"save" | "cancel" | "replace" | null>(null), [reviewer, setReviewer] = useState("");
  const [reason, setReason] = useState<Reason>("WRONG_SELECTION"), [reloadError, setReloadError] = useState<Error | null>(null);
  const mandatory = row.relationship === "SELF" || row.relationship === "MANAGER";
  const mutation = useMutation({ mutationFn: async () => {
    const dueChanged = due !== localDate(row.due_at);
    const effectiveDue = dueChanged ? toUtc(due) : row.due_at;
    if (action === "cancel") return feedbackApi.cancel(row.id, { ...versions(row), reason_code: reason });
    if (action === "replace") return feedbackApi.replace(row.id, { ...versions(row), reviewer_id: reviewer, due_at: effectiveDue, reason_code: reason });
    return feedbackApi.update(row.id, { ...versions(row), required: mandatory || required, ...(dueChanged || row.status === "CANCELLED" ? { due_at: effectiveDue } : {}), ...(row.status === "CANCELLED" ? { status: "OPEN" as const } : {}) });
  }, onSuccess: async (result) => { setRow(result); setAction(null); setDue(localDate(result.due_at)); setRequired(result.required); await saved(); } });
  const reload = async () => { try { setRow(await feedbackApi.adminDetail(row.id)); setAction(null); mutation.reset(); setReloadError(null); } catch (e) { setReloadError(e as Error); } };
  return <section ref={panel} tabIndex={-1} className="auth-card wide" aria-label="Chi tiết phân công"><div className="section-heading"><h2>{row.reviewer_name} · {relationships[row.relationship]}</h2><button className="secondary" onClick={close}>Đóng chi tiết</button></div><p>{statuses[row.status]} · {row.employee_code} · {row.display_name}</p>
    {row.submission ? <SubmissionContent {...row.submission} /> : row.cycle_status !== "ACTIVE" || row.finalized ? <p>Phân công không còn được chỉnh sửa.</p> : <>
      <div className="form-grid"><div><label htmlFor="edit-assignment-due">Hạn gửi mới (múi giờ thiết bị)</label><input id="edit-assignment-due" type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} disabled={mutation.isPending} /><label className="checkbox-label"><input type="checkbox" checked={mandatory || required} disabled={mandatory || mutation.isPending} onChange={(e) => setRequired(e.target.checked)} />Phản hồi bắt buộc</label></div><div><label htmlFor="assignment-reason">Lý do hủy / thay người</label><select id="assignment-reason" value={reason} onChange={(e) => setReason(e.target.value as Reason)}><option value="WRONG_SELECTION">Chọn nhầm người</option><option value="REVIEWER_UNAVAILABLE">Người đánh giá không thể tham gia</option><option value="NO_LONGER_REQUIRED">Không còn cần phản hồi tùy chọn</option></select></div></div>
      <div className="row-actions"><button disabled={mutation.isPending} onClick={() => setAction("save")}>{row.status === "CANCELLED" ? "Khôi phục phân công" : "Lưu phân công"}</button>{row.status === "OPEN" && !row.required && <button className="secondary" disabled={mutation.isPending} onClick={() => setAction("cancel")}>Hủy phân công tùy chọn</button>}{row.status === "OPEN" && !mandatory && <button className="secondary" disabled={mutation.isPending} onClick={() => setAction("replace")}>Thay người đánh giá</button>}</div>
      {action && <section className="confirmation"><h3>Xác nhận {action === "cancel" ? "hủy phân công" : action === "replace" ? "thay người đánh giá" : row.status === "CANCELLED" ? "khôi phục phân công" : "lưu thay đổi"}</h3>
        {action === "replace" && <><p>Giữ quan hệ và tính bắt buộc; hủy người cũ và giao người mới trong cùng thao tác.</p><ReviewerPicker participantId={row.participant_id} relationship={row.relationship} value={reviewer} onChange={setReviewer} allowCancelled /></>}
        <div className="row-actions"><button disabled={mutation.isPending || (action === "replace" && !reviewer) || (!!due && !Number.isFinite(Date.parse(due)))} onClick={() => mutation.mutate()}>Xác nhận thao tác</button><button className="secondary" disabled={mutation.isPending} onClick={() => setAction(null)}>Quay lại</button></div></section>}
    </>}
    {mutation.isError && <FeedbackError error={mutation.error} reload={() => { void reload(); }} />}{reloadError && <FeedbackError error={reloadError} />}
  </section>;
}
