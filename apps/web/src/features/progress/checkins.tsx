"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useId, useState } from "react";
import { useAuth } from "../auth/auth-provider";
import { Pagination } from "../organization/shared";
import { workApi } from "../work-management/api";
import { progressApi, type Checkin, type Followup, type Metrics } from "./api";
import { Decision, displayDate, ErrorMessage, History, labels, localInput, ProgressModal, Tabs, useProgressCommand, type Dirty } from "./shared";

export function CheckinEditor({metrics, dirty, saved}: {metrics: Metrics; dirty: Dirty; saved: (row: Checkin) => void}) {
  const id = useId();
  const plan = useQuery({queryKey: ["work-management", "plan", metrics.plan_id], queryFn: () => workApi.plan(metrics.plan_id)});
  const [title, setTitle] = useState("Rà soát tiến trình và hỗ trợ");
  const [scheduled, setScheduled] = useState(() => localInput(new Date(Date.now() + 86400000).toISOString()));
  const [start, setStart] = useState(""), [end, setEnd] = useState("");
  const [review, setReview] = useState(false);
  const mutation = useProgressCommand<Checkin>((row) => {dirty(false); saved(row);});
  const periodStart = start || plan.data?.start_date || "";
  const periodEnd = end || (plan.data ? [plan.data.end_date, new Date().toLocaleDateString("en-CA")].sort()[0] : "");
  return <form className="work-form" onChange={() => {dirty(true); setReview(false);}} onSubmit={(e) => {e.preventDefault(); setReview(true);}}>
    <p>Chọn lịch cụ thể và khoảng công việc cần rà soát. Hệ thống không tự tạo các cuộc họp khi không có người xác nhận.</p><ErrorMessage error={plan.error} />
    <label htmlFor={`${id}-title`}>Tên buổi rà soát</label><input id={`${id}-title`} required maxLength={200} value={title} disabled={mutation.isPending} onChange={(e) => setTitle(e.target.value)} />
    <label htmlFor={`${id}-scheduled`}>Lịch hẹn</label><input id={`${id}-scheduled`} type="datetime-local" required value={scheduled} disabled={mutation.isPending} onChange={(e) => setScheduled(e.target.value)} /><p className="help-text">Múi giờ nhập: {Intl.DateTimeFormat().resolvedOptions().timeZone}. Lịch được lưu theo UTC.</p>
    <div className="row-actions"><button type="button" className="secondary" disabled={mutation.isPending} onClick={() => {setScheduled(localInput(new Date(Date.now() + 7 * 86400000).toISOString())); dirty(true); setReview(false);}}>Gợi ý sau 7 ngày</button><button type="button" className="secondary" disabled={mutation.isPending} onClick={() => {setScheduled(localInput(new Date(Date.now() + 14 * 86400000).toISOString())); dirty(true); setReview(false);}}>Gợi ý sau 14 ngày</button></div>
    <label htmlFor={`${id}-start`}>Rà soát từ ngày</label><input id={`${id}-start`} type="date" required min={plan.data?.start_date} max={plan.data?.end_date} value={periodStart} disabled={mutation.isPending} onChange={(e) => setStart(e.target.value)} /><label htmlFor={`${id}-end`}>Rà soát đến ngày</label><input id={`${id}-end`} type="date" required min={periodStart} max={plan.data?.end_date} value={periodEnd} disabled={mutation.isPending} onChange={(e) => setEnd(e.target.value)} />
    <ErrorMessage error={mutation.error} /><button type="submit" disabled={mutation.isPending || plan.isPending}>Xem lại lịch hẹn</button>{review && <div className="confirmation"><strong>{title}</strong><p>{displayDate(new Date(scheduled).toISOString())}<br />Khoảng rà soát: {periodStart} → {periodEnd}</p><button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate({path: `progress/plans/${metrics.plan_id}/checkins`, body: {expected_version: metrics.plan_version, title, scheduled_at: new Date(scheduled).toISOString(), period_start: periodStart, period_end: periodEnd}})}>Tạo lịch và thông báo</button><button type="button" className="secondary" onClick={() => setReview(false)}>Tiếp tục chỉnh sửa</button></div>}
  </form>;
}

export function CheckinDetail({id, close}: {id: string; close: () => void}) {
  const [page, setPage] = useState(1), [tab, setTab] = useState(0);
  const query = useQuery({queryKey: ["checkins", "detail", id, page], queryFn: () => progressApi.checkin(id, page)});
  const {user} = useAuth();
  const row = query.data;
  const manager = !!row && row.manager_id === user?.id;
  return <ProgressModal title="Check-in và hỗ trợ" close={close}>{(dirty) => <><ErrorMessage error={query.error} />{query.isPending && <p role="status">Đang tải cuộc rà soát…</p>}{row && <><p className="eyebrow">{labels[row.status]} · {displayDate(row.scheduled_at)}</p><h3>{row.title}</h3><p>Khoảng công việc: {row.period_start} → {row.period_end}</p><Tabs prefix="checkin" names={["Chuẩn bị", "Biên bản", "Hành động", "Lịch sử"]} active={tab} change={setTab} />
    <section role="tabpanel" id="checkin-panel-0" aria-labelledby="checkin-tab-0" hidden={tab !== 0}><Preparation key={row.id} row={row} dirty={dirty} /><h3>Nội dung đã chia sẻ để chuẩn bị</h3>{row.preparations?.filter((p) => p.shared).map((p) => <article className="work-card" key={p.author_id}><strong>{p.author_id === row.manager_id ? "Quản lý" : "Nhân viên"}</strong><p className="work-prose">{p.body}</p></article>)}{manager && row.status !== "PUBLISHED" && <Decision path={`checkins/${row.id}/actions`} version={row.version} publication={row.publication} actions={row.actions.filter((a) => ["open", "reschedule", "cancel"].includes(a))} dirty={dirty} />}</section>
    <section role="tabpanel" id="checkin-panel-1" aria-labelledby="checkin-tab-1" hidden={tab !== 1}><p className="help-text">Xác nhận đã đọc không phải đồng ý đánh giá. Câu hỏi chưa thống nhất được giữ trong lịch sử.</p>{row.clarification_pending && <p className="work-warning">Nhân viên đang chờ quản lý phản hồi bằng phụ lục.</p>}{row.publications?.map((p) => <article className="work-card" key={p.number}><h4>{p.number === 1 ? "Biên bản gốc" : `Phụ lục ${p.number - 1}`} · {displayDate(p.created_at)}</h4><p className="work-prose">{p.body}</p>{p.preparations.map((s) => <details key={s.author_id}><summary>Phần chuẩn bị đã chia sẻ tại lúc công bố</summary><p className="work-prose">{s.body}</p></details>)}</article>)}{row.snapshot && <article className="work-card"><h4>Số liệu đã biết tại lúc công bố</h4><small>Phiên bản {row.snapshot.version} · {displayDate(row.snapshot.known_at)}</small>{row.snapshot.goals.map((g) => <p key={g.goal_id}>{g.name}: <strong>{g.actual !== null ? `${g.actual} ${g.unit}` : "Chưa đủ dữ liệu xác minh"}</strong></p>)}<Link href={`/work-management?tab=measurements&snapshot=${row.snapshot.id}&plan_ref=${row.plan_id}`}>Đối chiếu nguồn tại mốc này</Link></article>}<Decision path={`checkins/${row.id}/actions`} version={row.version} publication={row.publication} actions={row.actions.filter((a) => ["publish", "acknowledge", "clarify", "addendum"].includes(a))} dirty={dirty} />{row.status === "PUBLISHED" && <p>{row.acknowledged_publication === row.publication ? "Nhân viên đã đọc đúng bản mới nhất." : "Chưa xác nhận đã đọc bản mới nhất."}</p>}</section>
    <section role="tabpanel" id="checkin-panel-2" aria-labelledby="checkin-tab-2" hidden={tab !== 2}><p>Hỗ trợ có người nhận và hạn; người còn lại kiểm tra hoàn thành. Hành động này không tự tạo điểm KPI.</p>{row.actions.includes("create_followup") && <FollowupEditor row={row} dirty={dirty} />}<div className="work-cards">{row.followups?.items.map((a) => <article className="work-card" key={a.id}><h4>{a.body}</h4><span className="work-badge">{labels[a.status]}</span><p>Người thực hiện: {a.owner_id === row.manager_id ? "Quản lý hỗ trợ" : "Nhân viên"}<br />Người kiểm tra: {a.reviewer_id === row.manager_id ? "Quản lý" : "Nhân viên"}<br />Hạn: {displayDate(a.due_at)}</p>{a.overdue && <p className="work-warning">Đã quá hạn · cần phối hợp, không tự trừ điểm.</p>}<Decision path={`checkin-actions/${a.id}/actions`} version={a.version} actions={[...a.actions, ...(manager && row.actions_open !== false && !["DONE", "CANCELLED"].includes(a.status) ? ["cancel"] : [])]} dirty={dirty} /></article>)}</div>{!row.followups?.total && <p>Chưa có hành động hỗ trợ được giao.</p>}</section>
    <section role="tabpanel" id="checkin-panel-3" aria-labelledby="checkin-tab-3" hidden={tab !== 3}><History items={row.history?.items ?? []} /></section>
    <Pagination page={page} total={Math.max(row.publication, row.history?.total ?? 0, row.followups?.total ?? 0)} pending={query.isFetching} onPage={setPage} />
  </>}</>}</ProgressModal>;
}

function Preparation({row, dirty}: {row: Checkin; dirty: Dirty}) {
  const {user} = useAuth();
  const id = useId();
  const own = row.preparations?.find((p) => p.author_id === user?.id);
  const [body, setBody] = useState(own?.body ?? ""), [shared, setShared] = useState(own?.shared ?? false);
  const [version, setVersion] = useState(own?.version ?? 1), [review, setReview] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const mutation = useProgressCommand<Checkin>((saved) => {setVersion(saved.preparations?.find((p) => p.author_id === user?.id)?.version ?? version); setReview(false); setHasChanges(false); dirty(false, "preparation");});
  const stale = !!own && own.version > version;
  return <form className="work-form" onChange={() => {dirty(true, "preparation"); setHasChanges(true); setReview(false);}} onSubmit={(e) => {e.preventDefault(); setReview(true);}}>
    {!row.can_prepare && <p role="status" className="work-warning">Phần chuẩn bị đã khóa. Nội dung riêng và bản nhập chưa lưu được giữ để bạn đọc hoặc sao chép; không tự chia sẻ vào biên bản.</p>}
    <h3>Phần chuẩn bị của tôi</h3><p>Đã làm gì? Đang vướng gì? Cần người còn lại hỗ trợ điều gì? Không cần chép lại số KPI.</p>{stale && <div className="work-warning" role="status">Có bản chuẩn bị mới từ phiên khác. Bản nhập này được giữ. <button type="button" onClick={() => {setVersion(own.version); setReview(false);}}>Đã xem phiên bản mới</button></div>}
    <label htmlFor={`${id}-body`}>Nội dung chuẩn bị</label><textarea id={`${id}-body`} required maxLength={6000} value={hasChanges ? body : own?.body ?? body} disabled={mutation.isPending} readOnly={!row.can_prepare} onChange={(e) => setBody(e.target.value)} /><label className="checkbox-label"><input type="checkbox" checked={shared} disabled={mutation.isPending || !row.can_prepare} onChange={(e) => setShared(e.target.checked)} />Cho người còn lại trong cuộc check-in xem phần này</label><p className="help-text">{shared ? "Sẽ chia sẻ với người còn lại sau khi lưu. HR không đọc nội dung này." : "Bản riêng của bạn; chưa chia sẻ cho người còn lại hoặc HR."}</p>
    <ErrorMessage error={mutation.error} /><button type="submit" disabled={mutation.isPending || stale || !row.can_prepare}>Xem lại phần chuẩn bị</button>{review && <div className="confirmation"><strong>{shared ? "Lưu và chia sẻ nội dung" : "Lưu riêng cho tôi"}</strong><p className="work-prose">{body}</p><button type="button" disabled={mutation.isPending || stale || !row.can_prepare} onClick={() => mutation.mutate({path: `checkins/${row.id}/preparation`, body: {expected_version: version, body, shared}})}>Xác nhận lưu phần chuẩn bị</button><button type="button" className="secondary" onClick={() => setReview(false)}>Tiếp tục chỉnh sửa</button></div>}
  </form>;
}

function FollowupEditor({row, dirty}: {row: Checkin; dirty: Dirty}) {
  const id = useId();
  const [open, setOpen] = useState(false), [body, setBody] = useState("");
  const [owner, setOwner] = useState(row.owner_id), [due, setDue] = useState(() => localInput(new Date(Date.now() + 86400000).toISOString()));
  const [replacement, setReplacement] = useState("");
  const [review, setReview] = useState(false), [expected, setExpected] = useState(row.version);
  const mutation = useProgressCommand<Followup>(() => {setOpen(false); setReview(false); setBody(""); setReplacement(""); dirty(false, "followup");});
  const stale = row.version > expected;
  if (!open) return <button type="button" className="secondary" onClick={() => {setExpected(row.version); setOpen(true);}}>Giao hành động hỗ trợ</button>;
  return <form className="work-form" onChange={() => {dirty(true, "followup"); setReview(false);}} onSubmit={(e) => {e.preventDefault(); setReview(true);}}>
    <h3>Hành động cần thực hiện sau check-in</h3>{stale && <div role="status" className="work-warning">Cuộc rà soát vừa cập nhật. <button type="button" onClick={() => {setExpected(row.version); setReview(false);}}>Đã xem trạng thái mới</button></div>}
    <label htmlFor={`${id}-body`}>Đầu ra / hỗ trợ cần có</label><textarea id={`${id}-body`} required maxLength={6000} value={body} disabled={mutation.isPending} onChange={(e) => setBody(e.target.value)} /><label htmlFor={`${id}-owner`}>Người chịu trách nhiệm</label><select id={`${id}-owner`} value={owner} disabled={mutation.isPending} onChange={(e) => setOwner(e.target.value)}><option value={row.owner_id}>Nhân viên thực hiện · quản lý kiểm tra</option>{row.manager_id && <option value={row.manager_id}>Quản lý hỗ trợ · nhân viên xác nhận</option>}</select><label htmlFor={`${id}-due`}>Hạn hỗ trợ</label><input id={`${id}-due`} type="datetime-local" required value={due} max={localInput(row.verification_due_at)} disabled={mutation.isPending} onChange={(e) => setDue(e.target.value)} />
    {row.followups?.items.some((a) => a.status === "CANCELLED") && <><label htmlFor={`${id}-replacement`}>Thay thế hành động đã hủy (nếu có)</label><select id={`${id}-replacement`} value={replacement} onChange={(e) => setReplacement(e.target.value)}><option value="">Hành động mới</option>{row.followups.items.filter((a) => a.status === "CANCELLED").map((a) => <option key={a.id} value={a.id}>{a.body}</option>)}</select></>}
    <ErrorMessage error={mutation.error} /><button type="submit" disabled={mutation.isPending || stale || !row.actions.includes("create_followup")}>Xem lại hành động hỗ trợ</button>{review && <div className="confirmation"><p className="work-prose">{body}</p><p>{owner === row.manager_id ? "Quản lý thực hiện, nhân viên kiểm tra." : "Nhân viên thực hiện, quản lý kiểm tra."}</p><button type="button" disabled={mutation.isPending || stale || !row.actions.includes("create_followup")} onClick={() => mutation.mutate({path: `checkins/${row.id}/follow-ups`, body: {expected_version: expected, body, owner_id: owner, due_at: new Date(due).toISOString(), replaces_id: replacement || null}})}>Giao và thông báo người nhận</button><button type="button" className="secondary" onClick={() => setReview(false)}>Tiếp tục chỉnh sửa</button></div>}
  </form>;
}
